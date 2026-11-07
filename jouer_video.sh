#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Usage: jouer_video.sh [--populaire] requete

if [[ "${1:-}" == "--populaire" ]]; then
    # Remove the option and keep the rest as the query
    shift
    q="$*"

    # Get the most viewed video among the top 10 results
    line=$(yt-dlp --flat-playlist --print "%(view_count)s|%(id)s|%(title)s" "ytsearch10:$q" 2>/dev/null |
           sed 's/^NA/0/' |
           sort -t"|" -k1,1nr |
           head -n1)

    if [[ -z "$line" ]]; then
        echo "Aucune video trouvee"
        exit 1
    fi

    # Extract fields
    views="${line%%|*}"
    rest="${line#*|}"
    id="${rest%%|*}"
    title="${rest#*|}"

    echo "Titre: $title, Vues: $views"
else
    q="$*"
    id=$(yt-dlp --flat-playlist --print "%(id)s" "ytsearch1:$q" 2>/dev/null | head -n1)

    if [[ -z "$id" ]]; then
        echo "Aucune video trouvee"
        exit 1
    fi
    title=""
fi

# Open the video in Brave browser
am start -a android.intent.action.VIEW -d "https://www.youtube.com/watch?v=$id&autoplay=1" -p com.brave.browser >/dev/null

# Show what is being played
if [[ -n "${title:-}" ]]; then
    echo "Lecture en ligne : $title $id"
else
    echo "Lecture en ligne : $id"
fi
