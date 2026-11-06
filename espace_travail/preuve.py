import os
import datetime

# Récupérer le PID du processus actuel
pid = os.getpid()
# Obtenir l'heure actuelle avec secondes
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Chemin du fichier de sortie
output_path = os.path.join(os.path.dirname(__file__), 'preuve.txt')

# Écrire le PID et l'heure dans le fichier
with open(output_path, 'w') as f:
    f.write(f'PID: {pid}\n')
    f.write(f'Heure: {now}\n')

# Afficher le contenu sur la sortie standard
print(f'PID: {pid}')
print(f'Heure: {now}')
