#!/data/data/com.termux/files/usr/bin/bash
q="$*"
id=$(yt-dlp --flat-playlist --print "%(id)s" "ytsearch1:$q" 2>/dev/null | head -n 1)
[ -z "$id" ] && { echo "Aucune video trouvee"; exit 1; }
am start -a android.intent.action.VIEW -d "https://www.youtube.com/watch?v=$id&autoplay=1" -p com.brave.browser >/dev/null
echo "Lecture : $id"
