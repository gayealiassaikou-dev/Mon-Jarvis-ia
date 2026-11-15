"""Dashboard Flask - monitoring Jarvis."""
import os
import re
from collections import Counter
from flask import Flask, jsonify, render_template_string

from core.mission_manager import MissionManager
from core import budget_guard

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Jarvis Dashboard</title>
<style>
body { font-family: -apple-system, sans-serif; background: #0a0e1a; color: #e0e6ed; margin: 0; padding: 20px; }
h1 { color: #4fc3f7; border-bottom: 2px solid #4fc3f7; padding-bottom: 10px; }
h2 { color: #81c784; margin-top: 30px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; }
.card { background: #151b2d; border-left: 4px solid #4fc3f7; padding: 15px; border-radius: 6px; }
.card h3 { margin: 0 0 8px 0; color: #4fc3f7; font-size: 14px; text-transform: uppercase; }
.card .val { font-size: 28px; font-weight: bold; }
.card.warn { border-left-color: #ffb74d; }
.card.danger { border-left-color: #e57373; }
.card.ok { border-left-color: #81c784; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #2a3142; font-size: 13px; }
th { color: #4fc3f7; }
.badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
.badge.terminee { background: #1b5e20; color: #a5d6a7; }
.badge.en_cours { background: #e65100; color: #ffcc80; }
.badge.bloquee { background: #b71c1c; color: #ef9a9a; }
.badge.nouvelle { background: #0d47a1; color: #90caf9; }
.badge.annulee { background: #424242; color: #bdbdbd; }
button { background: #4fc3f7; color: #0a0e1a; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 20px; }
button:hover { background: #29b6f6; }
</style></head>
<body>
<h1>🤖 Jarvis Dashboard</h1>
<p style="color:#78909c">Rafraîchissement automatique toutes les 5 secondes</p>

<h2>Budget du jour</h2>
<div class="grid">
  <div class="card {% if budget.restant_appels < 50 %}danger{% elif budget.restant_appels < 150 %}warn{% else %}ok{% endif %}">
    <h3>Appels IA</h3><div class="val">{{ budget.appels }} / {{ budget.limite_appels }}</div>
    <small>Restant : {{ budget.restant_appels }}</small>
  </div>
  <div class="card {% if budget.restant_tokens < 50000 %}danger{% elif budget.restant_tokens < 150000 %}warn{% else %}ok{% endif %}">
    <h3>Tokens estimés</h3><div class="val">{{ "{:,}".format(budget.tokens_estimes) }}</div>
    <small>Restant : {{ "{:,}".format(budget.restant_tokens) }}</small>
  </div>
</div>

<h2>Missions</h2>
<div class="grid">
  {% for statut, nb in stats.items() %}
  <div class="card"><h3>{{ statut }}</h3><div class="val">{{ nb }}</div></div>
  {% endfor %}
</div>

<h2>Dernières missions (10)</h2>
<table><tr><th>ID</th><th>Nom</th><th>Statut</th><th>Priorité</th></tr>
{% for m in missions %}
<tr><td><code>{{ m.id }}</code></td><td>{{ m.nom[:60] }}</td>
<td><span class="badge {{ m.statut }}">{{ m.statut }}</span></td><td>{{ m.priorite }}</td></tr>
{% endfor %}
</table>

<h2>Latences récentes (jarvis.log)</h2>
<table><tr><th>Horodatage</th><th>Type</th><th>Durée</th></tr>
{% for l in latences %}
<tr><td>{{ l.ts }}</td><td>{{ l.type }}</td><td>{{ l.duree }}</td></tr>
{% endfor %}
</table>

<button onclick="location.reload()">🔄 Rafraîchir</button>
<script>setTimeout(()=>location.reload(), 5000);</script>
</body></html>
"""


def _lire_latences(max_lignes=15):
    chemin = "jarvis.log"
    if not os.path.exists(chemin):
        return []
    resultats = []
    with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
        lignes = f.readlines()[-200:]
    for ligne in reversed(lignes):
        m = re.search(r"\[(.+?)\].*?\[PERFORMANCE\] (.+?) : ([\d.]+ s)", ligne)
        if m:
            resultats.append({"ts": m.group(1), "type": m.group(2), "duree": m.group(3)})
        if len(resultats) >= max_lignes:
            break
    return resultats


@app.route("/")
def index():
    mm = MissionManager()
    missions_all = mm.lister_missions()
    stats = dict(Counter(m["statut"] for m in missions_all))
    missions_recentes = sorted(
        missions_all, key=lambda m: m.get("date_maj", m.get("date_creation", "")), reverse=True
    )[:10]
    return render_template_string(
        PAGE,
        budget=budget_guard.etat(),
        stats=stats,
        missions=missions_recentes,
        latences=_lire_latences(),
    )


@app.route("/api/etat")
def api_etat():
    mm = MissionManager()
    missions = mm.lister_missions()
    return jsonify({
        "budget": budget_guard.etat(),
        "missions_total": len(missions),
        "missions_par_statut": dict(Counter(m["statut"] for m in missions)),
        "latences": _lire_latences(5),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
