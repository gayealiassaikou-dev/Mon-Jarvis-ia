import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

MAX_OCTETS = 1_000_000
MAX_CARACTERES = 12000
MAX_REDIRECTIONS = 3
EN_TETES = {"User-Agent": "Mozilla/5.0 (compatible; SamSarr/1.0)"}


def _url_sure(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return "URL invalide (http ou https uniquement)."
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except OSError:
        return "Nom de domaine introuvable."
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            return "adresse interne refusée."
    return None


def lire_page_web(url):
    if not isinstance(url, str) or not url.strip():
        return "Erreur : URL absente."
    url = url.strip()
    try:
        for _ in range(MAX_REDIRECTIONS + 1):
            refus = _url_sure(url)
            if refus:
                return f"Erreur : accès refusé, {refus}"
            r = requests.get(url, headers=EN_TETES, timeout=15,
                             stream=True, allow_redirects=False)
            if r.is_redirect:
                url = urljoin(url, r.headers.get("Location", ""))
                r.close()
                continue
            break
        else:
            return "Erreur : trop de redirections."
        if r.status_code != 200:
            return f"Erreur : la page a répondu HTTP {r.status_code}."
        type_ = r.headers.get("Content-Type", "").lower()
        if "text/html" not in type_ and "text/plain" not in type_:
            return f"Erreur : type de contenu non pris en charge ({type_ or 'inconnu'})."
        brut = b""
        for morceau in r.iter_content(65536):
            brut += morceau
            if len(brut) > MAX_OCTETS:
                break
        r.close()
        soupe = BeautifulSoup(brut.decode(r.encoding or "utf-8", errors="replace"), "html.parser")
        for balise in soupe(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
            balise.decompose()
        titre = soupe.title.get_text(strip=True) if soupe.title else ""
        lignes = [l.strip() for l in soupe.get_text("\n").splitlines() if l.strip()]
        texte = "\n".join(lignes)
        if not texte:
            return "Erreur : aucun texte lisible sur cette page."
        sortie = f"Page : {url}\nTitre : {titre}\n\n{texte}"
        if len(sortie) > MAX_CARACTERES:
            sortie = sortie[:MAX_CARACTERES] + "\n[... texte tronqué]"
        return sortie
    except requests.RequestException as exc:
        return f"Erreur : impossible de charger la page : {exc}"
    except Exception as exc:
        return f"Erreur : lecture de la page échouée : {exc}"
