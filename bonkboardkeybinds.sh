# 1. Define variables for names, keys, and paths
SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
BASE_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
declare -a NEW_PATHS

create_binding() {
    local id="$1" local name="$2" local key="$3" local cmd="$4"
    local path="${BASE_PATH}/${id}/"
    gsettings set "${SCHEMA}:${path}" name "${name}"
    gsettings set "${SCHEMA}:${path}" binding "${key}"
    gsettings set "${SCHEMA}:${path}" command "${cmd}"
    NEW_PATHS+=("${path}")
}

echo "Configuring Bonkboard system keybindings..."

# 2. Generate Sound Buttons (Alt+1 -> Sound 0, Alt+2 -> Sound 1 ... Alt+0 -> Sound 9)
for i in {1..9}; do
    sound_idx=$((i - 1))
    create_binding "bonkboard_s${sound_idx}" "BonkboardSound${i}" "<Alt>${i}" "bash -c 'echo -n \"${sound_idx}\" > /dev/udp/127.0.0.1/12345'"
done
create_binding "bonkboard_s9" "BonkboardSound0" "<Alt>0" "bash -c 'echo -n \"9\" > /dev/udp/127.0.0.1/12345'"

# 3. Generate Stop and Tab Switching Buttons
create_binding "bonkboard_stop" "BonkboardStop" "<Alt>space" "bash -c 'echo -n \"stop\" > /dev/udp/127.0.0.1/12345'"
create_binding "bonkboard_tab_prev" "BonkboardPrevTab" "<Alt>q" "bash -c 'echo -n \"tab:prev\" > /dev/udp/127.0.0.1/12345'"
create_binding "bonkboard_tab_next" "BonkboardNextTab" "<Alt>e" "bash -c 'echo -n \"tab:next\" > /dev/udp/127.0.0.1/12345'"

# 4. Clean and merge with existing bindings safely
CURRENT_BINDINGS=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)
if [[ "$CURRENT_BINDINGS" == "@as []" || "$CURRENT_BINDINGS" == "[]" ]]; then
    CLEAN_BINDINGS=""
else
    CLEAN_BINDINGS=$(echo "$CURRENT_BINDINGS" | tr -d "[]' ")
fi

IFS=',' read -r -a BINDINGS_ARRAY <<< "$CLEAN_BINDINGS"
for p in "${NEW_PATHS[@]}"; do
    if [[ ! " ${BINDINGS_ARRAY[*]} " =~ " ${p} " ]]; then
        BINDINGS_ARRAY+=("${p}")
    fi
done

FORMATTED_ARRAY="["
for ((i=0; i<${#BINDINGS_ARRAY[@]}; i++)); do
    if [[ -n "${BINDINGS_ARRAY[i]}" ]]; then
        FORMATTED_ARRAY+="'${BINDINGS_ARRAY[i]}'"
        [[ $i -lt $((${#BINDINGS_ARRAY[@]} - 1)) ]] && FORMATTED_ARRAY+=", "
    fi
done
FORMATTED_ARRAY+="]"

gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$FORMATTED_ARRAY"
echo "Success! 13 keybindings configured cleanly."
