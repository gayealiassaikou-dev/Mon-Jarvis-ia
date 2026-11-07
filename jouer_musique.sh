#!/data/data/com.termux/files/usr/bin/bash
q="$*"
dossier="$(cd "$(dirname "$0")" && pwd)"
fichier=$(python "$dossier/chercher_local.py" "$q" 2>/dev/null | head -n 1)
if [ -n "$fichier" ]; then
  if [[ "$fichier" == "$HOME/storage/shared/"* ]]; then
    chemin_android="${fichier/#$HOME\/storage\/shared\//\/storage\/emulated\/0\/}"
    chemin_android="${chemin_android// /%20}"
    sortie=$(am start -a android.intent.action.VIEW -t audio/mpeg -d "file://$chemin_android" 2>&1)
    if echo "$sortie" | grep -qi "Starting" && ! echo "$sortie" | grep -qi "Error"; then
      echo "Lecture locale : $(basename "$fichier")"
      exit 0
    fi
    echo "Lecteur local indisponible ($sortie), passage en ligne"
  else
    termux-media-player stop >/dev/null 2>&1
    sortie=$(termux-media-player play "$fichier" 2>&1)
    if echo "$sortie" | grep -qi "playing"; then
      echo "Lecture locale : $(basename "$fichier")"
      exit 0
    fi
    echo "Lecteur local indisponible ($sortie), passage en ligne"
  fi
fi
id=$(yt-dlp --flat-playlist --print "%(id)s" "ytsearch1:$q" 2>/dev/null | head -n 1)
[ -z "$id" ] && { echo "Aucune video trouvee"; exit 1; }
am start -a android.intent.action.VIEW -d "https://www.youtube.com/watch?v=$id&autoplay=1" -p com.brave.browser >/dev/null
echo "Lecture en ligne : $id"
