"""Couche API multi-providers pour Jarvis - extrait de ai_engine.py."""
import json
import os
import time

import requests

from core.tools_schema import OUTILS_GEMINI, _convertir_outils_gemini


class AIProvidersMixin:
    """Methodes d'appel aux providers IA (OpenAI-compatibles + Gemini)."""

    def _post_avec_reessai_429(self, url, headers, payload, timeout):
        """POST avec patience sur les limites de debit (HTTP 429).

        Si le fournisseur indique un delai de reprise court (30 s max),
        on attend puis on refait le meme appel HTTP, 2 fois au plus.
        Rien n'est rejoue : l'appel refuse n'a produit aucune reponse.
        """
        import re
        import time

        reponse = requests.post(url, headers=headers, json=payload, timeout=timeout)
        for _ in range(2):
            if getattr(reponse, "status_code", None) != 429:
                break
            attente = None
            entetes = getattr(reponse, "headers", None) or {}
            try:
                valeur = entetes.get("retry-after")
                if valeur:
                    attente = float(valeur)
            except (TypeError, ValueError, AttributeError):
                attente = None
            if attente is None:
                trouve = re.search(
                    r"try again in ([0-9.]+)s",
                    str(getattr(reponse, "text", "") or ""),
                )
                if trouve:
                    attente = float(trouve.group(1))
            if attente is None or attente > 30:
                break
            time.sleep(attente + 1)
            reponse = requests.post(url, headers=headers, json=payload, timeout=timeout)
        return reponse

    def _appeler_openai_compatible(
    self,
    url,
    headers,
    model,
    message,
    contexte="",
    historique=None,
    outils=None,
    mode_action=False,
    timeout=15,
    parametres_supplementaires=None,
    on_chunk=None,
):
        messages = []
        if contexte:
            messages.append({"role": "system", "content": contexte})
        if historique:
            for echange in historique:
                messages.append({"role": "user", "content": echange["question"]})
                messages.append({"role": "assistant", "content": echange["reponse"]})
        messages.append({"role": "user", "content": message})

        # Streaming direct si on_chunk et pas d'outils forces
        if on_chunk is not None and not mode_action:
            try:
                payload_stream = {"model": model, "messages": messages, "stream": True}
                if parametres_supplementaires:
                    payload_stream.update(parametres_supplementaires)
                with requests.post(
                    url,
                    headers=headers,
                    json=payload_stream,
                    timeout=60,
                    stream=True,
                ) as r:
                    r.raise_for_status()
                    textes_stream = []
                    for ligne in r.iter_lines():
                        if not ligne:
                            continue
                        ligne_str = ligne.decode("utf-8") if isinstance(ligne, bytes) else ligne
                        if ligne_str.startswith("data: "):
                            ligne_str = ligne_str[6:]
                        if ligne_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(ligne_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            t = delta.get("content", "")
                            if t:
                                textes_stream.append(t)
                                try:
                                    on_chunk(t)
                                except Exception:
                                    pass
                        except Exception:
                            continue
                    if textes_stream:
                        return "".join(textes_stream)
            except Exception:
                # Fallback : mode classique
                pass

        # Le mode action force uniquement la premiere selection
        # d'un outil. Apres execution, le modele doit pouvoir
        # produire librement sa reponse finale sans etre force
        # a relancer un outil.
        for iteration in range(5):
            payload = {"model": model, "messages": messages}
            if parametres_supplementaires:
                payload.update(parametres_supplementaires)

            if outils:
                payload["tools"] = outils

                if mode_action and iteration == 0:
                    payload["tool_choice"] = "required"
            reponse = self._post_avec_reessai_429(url, headers, payload, timeout)
            # Certains modeles repondent en texte alors que l'outil est impose :
            # l'API refuse alors la reponse (HTTP 400, tool_use_failed).
            # On relance une seule fois sans forcer l'outil.
            if (
                payload.get("tool_choice") == "required"
                and getattr(reponse, "status_code", None) == 400
                and "tool_use_failed" in (getattr(reponse, "text", "") or "")
            ):
                payload.pop("tool_choice", None)
                reponse = self._post_avec_reessai_429(url, headers, payload, timeout)
            try:
                reponse.raise_for_status()
            except requests.HTTPError as erreur_http:
                statut = getattr(reponse, "status_code", "inconnu")
                try:
                    details = json.dumps(reponse.json(), ensure_ascii=False)
                except Exception:
                    details = getattr(reponse, "text", "") or str(erreur_http)
                details = str(details)[:1000]
                raise requests.HTTPError(
                    f"HTTP {statut}: {details}",
                    response=reponse,
                ) from erreur_http
            data = reponse.json()
            choix = data["choices"][0]["message"]

            if choix.get("tool_calls"):
                messages.append(choix)
                for appel in choix["tool_calls"]:
                    nom_fonction = appel["function"]["name"]

                    try:
                        arguments = json.loads(
                            appel["function"].get("arguments", "{}")
                        ) or {}

                    except json.JSONDecodeError as e:
                        resultat = (
                            "Erreur outil : arguments JSON invalides : "
                            f"{e}"
                        )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": appel["id"],
                            "content": str(resultat)
                        })

                        continue

                    except (TypeError, AttributeError) as e:
                        resultat = (
                            "Erreur outil : arguments de Tool Calling "
                            f"invalides : {type(e).__name__}: {e}"
                        )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": appel["id"],
                            "content": str(resultat)
                        })

                        continue

                    resultat = self._executer_outil(
                        nom_fonction,
                        arguments
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": appel["id"],
                        "content": str(resultat)
                    })
            else:
                contenu = choix.get("content")

                # Reponse vide sans aucune action engagee : on leve une
                # erreur pour que le routeur essaie le fournisseur suivant.
                # Si une action a deja ete engagee, on garde le comportement
                # actuel : ni rejeu ni fallback (anti-double-execution).
                if (
                    not isinstance(contenu, str) or not contenu.strip()
                ) and not getattr(self, "action_engagee", False):
                    raise Exception(
                        "Reponse vide du fournisseur "
                        "(content absent ou vide)."
                    )

                return contenu

        raise Exception("Trop d'appels d'outils enchaines.")

    def _demander_groq(self, message, contexte="", historique=None, on_chunk=None):
        def appeler_avec_cle(cle):
            headers = {
                "Authorization": f"Bearer {cle}",
                "Content-Type": "application/json"
            }
            return self._appeler_openai_compatible(
                self.url,
                headers,
                self.model,
                message,
                contexte,
                historique,
                outils=self._obtenir_outils_autorises(),
                mode_action=self.mode_action,
                on_chunk=on_chunk,
            )

        try:
            return appeler_avec_cle(self.api_key)
        except Exception:
            if (
                getattr(self, "action_engagee", False)
                or not self.api_key_1
                or self.api_key_1 == self.api_key
            ):
                raise
            return appeler_avec_cle(self.api_key_1)

    def _demander_openrouter(self, message, contexte="", historique=None, on_chunk=None):
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.openrouter_url,
            headers,
            self.openrouter_model,
            message,
            contexte,
            historique,
            outils=self._obtenir_outils_autorises(),
            mode_action=self.mode_action,
            on_chunk=on_chunk,
        )
    def _demander_mistral(self, message, contexte="", historique=None, on_chunk=None):
        headers = {
            "Authorization": f"Bearer {self.mistral_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.mistral_url,
            headers,
            self.mistral_model,
            message,
            contexte,
            historique,
            outils=self._obtenir_outils_autorises(),
            mode_action=self.mode_action,
            on_chunk=on_chunk,
        )

    def _demander_nvidia(self, message, contexte="", historique=None, on_chunk=None):
        fournisseur = self.providers.get("nvidia", {})
        cle = os.getenv(fournisseur.get("api_key_env", "NVIDIA_API_KEY"))
        headers = {
            "Authorization": f"Bearer {cle}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            fournisseur.get("url"),
            headers,
            fournisseur.get("model"),
            message,
            contexte,
            historique,
            outils=self._obtenir_outils_autorises(),
            mode_action=self.mode_action,
            on_chunk=on_chunk,
            timeout=20,
            parametres_supplementaires={
                "chat_template_kwargs": {"enable_thinking": False}
            },
        )

    def _demander_gemini(self, message, contexte="", historique=None, on_chunk=None):
        contents = []

        if historique:
            for echange in historique:
                contents.append({"role": "user", "parts": [{"text": echange["question"]}]})
                contents.append({"role": "model", "parts": [{"text": echange["reponse"]}]})

        contents.append({"role": "user", "parts": [{"text": message}]})

        payload = {"contents": contents, "tools": _convertir_outils_gemini(self._obtenir_outils_autorises())}
        payload["generationConfig"] = {"temperature": 0.1}
        payload["generationConfig"] = {"temperature": 0.1}
        if contexte:
            payload["systemInstruction"] = {"parts": [{"text": contexte}]}

        # Forcer l'appel d'outil au premier tour si mode_action
        if self.mode_action:
            payload["toolConfig"] = {
                "functionCallingConfig": {"mode": "ANY"}
            }

        url = self.gemini_url

        for iteration in range(5):
            if iteration > 0 and "toolConfig" in payload:
                payload["toolConfig"]["functionCallingConfig"]["mode"] = "AUTO"

            # Streaming uniquement si on_chunk fourni ET pas d'outils forces
            # (sinon on garde le mode classique pour detecter les functionCall)
            use_stream = on_chunk is not None and not self.mode_action and iteration == 0

            if use_stream:
                stream_url = url.replace(":generateContent", ":streamGenerateContent") + "?alt=sse"
                textes_stream = []
                try:
                    with requests.post(
                        stream_url,
                        headers={"x-goog-api-key": self.gemini_key},
                        json=payload,
                        timeout=60,
                        stream=True,
                    ) as r:
                        r.raise_for_status()
                        for ligne in r.iter_lines():
                            if not ligne:
                                continue
                            ligne_str = ligne.decode("utf-8") if isinstance(ligne, bytes) else ligne
                            if ligne_str.startswith("data: "):
                                ligne_str = ligne_str[6:]
                            if ligne_str.strip() == "[DONE]":
                                break
                            try:
                                import json as _json_s
                                chunk = _json_s.loads(ligne_str)
                                parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    t = p.get("text", "")
                                    if t:
                                        textes_stream.append(t)
                                        try:
                                            on_chunk(t)
                                        except Exception:
                                            pass
                            except Exception:
                                continue
                    if textes_stream:
                        return "".join(textes_stream)
                except Exception as _e_stream:
                    print(f"[Gemini stream] coupure : {_e_stream!r}", flush=True)
                    # Fallback : revenir au mode classique
                    pass

            reponse = requests.post(url, headers={"x-goog-api-key": self.gemini_key}, json=payload, timeout=15)
            reponse.raise_for_status()
            data = reponse.json()
            candidat = data["candidates"][0]["content"]

            appels_fonction = [p["functionCall"] for p in candidat.get("parts", []) if "functionCall" in p]

            if appels_fonction:
                contents.append(candidat)
                parts_resultats = []
                for appel in appels_fonction:
                    nom_fonction = appel["name"]
                    arguments = appel.get("args", {}) or {}
                    resultat = self._executer_outil(nom_fonction, arguments)
                    parts_resultats.append({
                        "functionResponse": {
                            "name": nom_fonction,
                            "response": {"resultat": str(resultat)}
                        }
                    })
                contents.append({"role": "user", "parts": parts_resultats})
                payload["contents"] = contents
            else:
                textes = [p.get("text", "") for p in candidat.get("parts", [])]
                return "".join(textes)

        raise Exception("Trop d'appels d'outils enchaines (Gemini).")
