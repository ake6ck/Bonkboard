#!/usr/bin/env python3

import os
import json
import subprocess
import shutil
import socket
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, Gdk


class BonkboardWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)

        self.set_title("Bonkboard")
        self.set_default_size(700, 500)

        self.app_config_dir = os.path.expanduser("~/.config/bonkboard")
        self.path_pointer_file = os.path.join(self.app_config_dir, "db_location.txt")
        self.store_file = self.get_database_path()

        self.active_sounds = {}

        self.setup_audio_routing()
        self.apply_theme_customizations()

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        
        # Create a standard flat button for the title
        title_btn = Gtk.Button(label="Bonkboard")
        title_btn.add_css_class("flat")
        title_btn.add_css_class("bonk-title-button")
        title_btn.set_focusable(False)
        
        # Link to the GitHub page when clicked
        def on_title_clicked(btn):
            launcher = Gtk.UriLauncher.new("https://github.com/ake6ck/Bonkboard")
            launcher.launch(self, None, None)
            
        title_btn.connect("clicked", on_title_clicked)
        header.set_title_widget(title_btn)
        
        add_tab_btn = Gtk.Button()
        add_tab_btn.set_icon_name("list-add-symbolic")
        add_tab_btn.set_tooltip_text("Create New Tab")
        add_tab_btn.connect("clicked", self.on_create_tab_clicked)
        header.pack_start(add_tab_btn)

        settings_btn = Gtk.Button()
        settings_btn.set_icon_name("preferences-system-symbolic")
        settings_btn.set_tooltip_text("Settings & Layout Database")
        settings_btn.connect("clicked", self.on_settings_clicked)
        header.pack_end(settings_btn)
        
        toolbar.add_top_bar(header)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )

        self.notebook = Gtk.Notebook()
        self.notebook.set_hexpand(True)
        self.notebook.set_vexpand(True)
        self.notebook.add_css_class("bonk-notebook")
        self.notebook.connect("switch-page", lambda nb, page, num: self.update_action_button_state())

        self.action_button = Gtk.Button(label="Add Audio File")
        self.action_button.add_css_class("pill")
        self.action_button.add_css_class("suggested-action")
        self.action_button.connect("clicked", self.on_action_button_clicked)

        content.append(self.notebook)
        content.append(self.action_button)

        toolbar.set_content(content)
        self.set_content(toolbar)

        file_drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        file_drop_target.connect("drop", self.on_desktop_files_dropped)
        self.add_controller(file_drop_target)

        self.load_stored_sounds()
        
        # Start our local communication server
        self.start_local_command_server()

    def apply_theme_customizations(self):
        css_provider = Gtk.CssProvider()
        css_code = """
            .bonk-notebook { border-radius: 12px; border: 1px solid rgba(0, 0, 0, 0.12); }
            .bonk-notebook header { background: transparent; border: none; box-shadow: none; padding-bottom: 2px; }
            .bonk-notebook header tabs { border: none; }
            .bonk-notebook header tabs tab { border-top-left-radius: 8px; border-top-right-radius: 8px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px; margin-right: 4px; padding: 6px 12px; }
            .bonk-notebook stack { border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; border-top-left-radius: 0px; border-top-right-radius: 0px; border-top: 1px solid rgba(0, 0, 0, 0.08); }
            .bonk-tab-container { padding: 12px; }
        """
        css_provider.load_from_data(css_code, len(css_code))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def start_local_command_server(self):
        """Runs a background UDP server allowing external OS shortcuts to communicate with the UI."""
        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(("127.0.0.1", 12345))
                while True:
                    data, addr = sock.recvfrom(1024)
                    msg = data.decode("utf-8").strip()
                    if msg == "stop":
                        GLib.idle_add(self.stop_all_sounds_action)
                    elif msg.startswith("tab:"):
                        tab_cmd = msg.split(":", 1)[1]
                        GLib.idle_add(self.switch_tab_by_command, tab_cmd)
                    elif msg.isdigit():
                        index = int(msg)
                        GLib.idle_add(self.play_sound_by_index, index)
            except Exception as e:
                print(f"IPC server error: {e}")
            finally:
                sock.close()

        threading.Thread(target=listen, daemon=True).start()

    def switch_tab_by_command(self, command):
        """Switches the current active notebook tab based on string criteria or index."""
        total_pages = self.notebook.get_n_pages()
        if total_pages <= 1:
            return

        current_page = self.notebook.get_current_page()

        if command == "next":
            next_page = (current_page + 1) % total_pages
            self.notebook.set_current_page(next_page)
        elif command == "prev":
            prev_page = (current_page - 1) % total_pages
            self.notebook.set_current_page(prev_page)
        elif command.isdigit():
            target_idx = int(command)
            if 0 <= target_idx < total_pages:
                self.notebook.set_current_page(target_idx)

    def play_sound_by_index(self, index):
        """Locates the path of a sound item on the current tab by physical grid position."""
        grid = self.get_current_sound_grid()
        if not grid:
            return
        
        count = 0
        child = grid.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.FlowBoxChild):
                if count == index:
                    button = child.get_child()
                    if button and hasattr(button, "file_path"):
                        self.on_toggle_sound(button.file_path)
                        return
                count += 1
            child = child.get_next_sibling()

    def get_database_path(self):
        os.makedirs(self.app_config_dir, exist_ok=True)
        default_path = os.path.join(self.app_config_dir, "bonkboard_store.json")
        if os.path.exists(self.path_pointer_file):
            try:
                with open(self.path_pointer_file, "r") as f:
                    custom_path = f.read().strip()
                    if custom_path: return custom_path
            except Exception: pass
        return default_path

    def setup_audio_routing(self):
        try:
            modules_check = subprocess.run(["pactl", "list", "modules", "short"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            loaded_modules = modules_check.stdout if modules_check.returncode == 0 else ""
            if "sink_name=BonkboardSink" not in loaded_modules:
                subprocess.run(["pactl", "load-module", "module-null-sink", "sink_name=BonkboardSink", "sink_properties=device.description=BonkboardVirtualSink"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if "source_name=BonkboardMic" not in loaded_modules:
                subprocess.run(["pactl", "load-module", "module-remap-source", "master=BonkboardSink.monitor", "source_name=BonkboardMic", "source_properties=device.description=BonkboardVirtualMic"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if "source=BonkboardSink.monitor" not in loaded_modules:
                subprocess.run(["pactl", "load-module", "module-loopback", "source=BonkboardSink.monitor"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Error executing audio configuration: {e}")

    def create_tab_page(self, tab_title):
        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.add_css_class("bonk-tab-container")

        grid = Gtk.FlowBox()
        grid.set_valign(Gtk.Align.START)
        grid.set_halign(Gtk.Align.FILL)
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_column_spacing(12)   
        grid.set_row_spacing(12)      
        grid.set_homogeneous(True)
        grid.set_max_children_per_line(6)
        scroller.set_child(grid)

        tab_label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=tab_title)
        tab_label_box.append(lbl)

        scroller.tab_label_text = lbl
        scroller.sound_grid = grid

        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect("pressed", self.on_tab_right_click, scroller)
        tab_label_box.add_controller(gesture)

        self.notebook.append_page(scroller, tab_label_box)
        return scroller

    def load_stored_sounds(self):
        while self.notebook.get_n_pages() > 0:
            self.notebook.remove_page(0)
        if os.path.exists(self.store_file):
            try:
                with open(self.store_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "tabs" in data:
                        tabs_data = data.get("tabs", {"Main": []})
                        for tab_name, sounds in tabs_data.items():
                            page = self.create_tab_page(tab_name)
                            for item in sounds:
                                if os.path.exists(item["path"]): self.add_sound_card_to_grid(page.sound_grid, item["path"], item["name"])
                    else:
                        sounds = data.get("sounds", []) if isinstance(data, dict) else data
                        page = self.create_tab_page("Main")
                        for item in sounds:
                            if os.path.exists(item["path"]): self.add_sound_card_to_grid(page.sound_grid, item["path"], item["name"])
            except Exception as e:
                print(f"Error loading library file: {e}")
        if self.notebook.get_n_pages() == 0:
            self.create_tab_page("Main")
        self.update_action_button_state()

    def save_current_order_to_store(self):
        tabs_data = {}
        for i in range(self.notebook.get_n_pages()):
            page = self.notebook.get_nth_page(i)
            tab_name = page.tab_label_text.get_text()
            sounds = []
            grid = page.sound_grid
            child = grid.get_first_child()
            while child is not None:
                if isinstance(child, Gtk.FlowBoxChild):
                    button = child.get_child()
                    if button and hasattr(button, "file_path") and hasattr(button, "file_name"):
                        sounds.append({"path": button.file_path, "name": button.file_name})
                child = child.get_next_sibling()
            tabs_data[tab_name] = sounds
        try:
            target_dir = os.dirname(self.store_file)
            if target_dir: os.makedirs(target_dir, exist_ok=True)
            with open(self.store_file, "w") as f: json.dump({"tabs": tabs_data}, f, indent=4)
        except Exception as e:
            print(f"Failed to write configuration to store: {e}")

    def get_current_sound_grid(self):
        current_idx = self.notebook.get_current_page()
        if current_idx != -1:
            return self.notebook.get_nth_page(current_idx).sound_grid
        return None

    def update_action_button_state(self):
        if len(self.active_sounds) > 0:
            self.action_button.set_label("Stop All Sounds")
            self.action_button.remove_css_class("suggested-action")
            self.action_button.add_css_class("destructive-action")
        else:
            self.action_button.set_label("Add Audio File")
            self.action_button.remove_css_class("destructive-action")
            self.action_button.add_css_class("suggested-action")

    def on_action_button_clicked(self, button):
        if len(self.active_sounds) > 0: self.stop_all_sounds_action()
        else: self.trigger_file_picker()

    def stop_all_sounds_action(self):
        active_paths = list(self.active_sounds.keys())
        for path in active_paths:
            proc = self.active_sounds.pop(path, None)
            if proc:
                try: proc.terminate(); proc.wait()
                except Exception: pass
        for i in range(self.notebook.get_n_pages()):
            page = self.notebook.get_nth_page(i)
            child = page.sound_grid.get_first_child()
            while child is not None:
                if isinstance(child, Gtk.FlowBoxChild):
                    btn = child.get_child()
                    if btn: btn.remove_css_class("destructive-action"); btn.add_css_class("suggested-action")
                child = child.get_next_sibling()
        self.update_action_button_state()

    def trigger_file_picker(self):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Audio Track")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        audio_filter = Gtk.FileFilter()
        audio_filter.set_name("Audio Files")
        audio_filter.add_suffix("mp3"); audio_filter.add_suffix("wav"); audio_filter.add_suffix("ogg"); audio_filter.add_suffix("m4a")
        filters.append(audio_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_sound_file_picked)

    def on_sound_file_picked(self, dialog, result):
        try:
            file_info = dialog.open_finish(result)
            grid = self.get_current_sound_grid()
            if file_info and grid:
                self.add_sound_card_to_grid(grid, file_info.get_path(), file_info.get_basename())
                self.save_current_order_to_store()
        except Exception as e:
            print(f"Error selecting file: {e}")

    def on_desktop_files_dropped(self, target, value, x, y):
        grid = self.get_current_sound_grid()
        if not grid: return False
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            supported_extensions = (".mp3", ".wav", ".ogg", ".m4a")
            added_any = False
            for gfile in files:
                path = gfile.get_path()
                if path and path.lower().endswith(supported_extensions):
                    self.add_sound_card_to_grid(grid, path, gfile.get_basename())
                    added_any = True
            if added_any:
                self.save_current_order_to_store()
                return True
        return False

    def add_sound_card_to_grid(self, grid, file_path, file_name):
        short_name = file_name if len(file_name) <= 18 else file_name[:15] + "..."
        sound_btn = Gtk.Button(label=short_name)
        sound_btn.set_size_request(130, 90)
        sound_btn.set_hexpand(True)
        sound_btn.file_path = file_path
        sound_btn.file_name = file_name
        sound_btn.add_css_class("suggested-action")
        sound_btn.connect("clicked", lambda b: self.on_toggle_sound(file_path))

        child = Gtk.FlowBoxChild()
        child.set_child(sound_btn)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(3)
        click_gesture.connect("pressed", self.on_sound_right_click, child, grid, sound_btn)
        sound_btn.add_controller(click_gesture)
        grid.append(child)

    def on_sound_right_click(self, gesture, n_press, x, y, child_widget, grid, sound_btn):
        popover = Gtk.Popover()
        popover.set_parent(gesture.get_widget())
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu_box.set_margin_start(4); menu_box.set_margin_end(4); menu_box.set_margin_top(4); menu_box.set_margin_bottom(4)
         
        rename_btn = Gtk.Button(label="Rename Track")
        rename_btn.add_css_class("flat")
        rename_btn.connect("clicked", self.on_rename_sound_clicked, sound_btn, popover)

        current_page = self.notebook.get_current_page()
        move_menu_btn = Gtk.Button(label="Move to Tab...")
        move_menu_btn.add_css_class("flat")
        
        move_popover = Gtk.Popover()
        move_popover.set_parent(move_menu_btn)
        move_popover.set_position(Gtk.PositionType.RIGHT)
        
        move_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        move_box.set_margin_start(4); move_box.set_margin_end(4); move_box.set_margin_top(4); move_box.set_margin_bottom(4)

        has_other_tabs = False
        for i in range(self.notebook.get_n_pages()):
            if i == current_page: continue
            has_other_tabs = True
            target_page = self.notebook.get_nth_page(i)
            target_btn = Gtk.Button(label=target_page.tab_label_text.get_text())
            target_btn.add_css_class("flat")
            target_btn.connect("clicked", self.on_move_sound_to_tab, grid, child_widget, target_page.sound_grid, popover)
            move_box.append(target_btn)

        if not has_other_tabs:
            no_tabs_lbl = Gtk.Label(label="No other tabs available")
            no_tabs_lbl.add_css_class("dim-label")
            move_box.append(no_tabs_lbl)

        move_popover.set_child(move_box)
        motion_ctrl = Gtk.EventControllerMotion.new()
        motion_ctrl.connect("enter", lambda ctrl, cx, cy: move_popover.popup())
        move_menu_btn.add_controller(motion_ctrl)

        delete_btn = Gtk.Button(label="Delete Track")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self.on_delete_sound_confirmed, grid, child_widget, sound_btn.file_path, popover)
         
        menu_box.append(rename_btn); menu_box.append(move_menu_btn); menu_box.append(delete_btn)
        popover.set_child(menu_box)
        popover.popup()

    def on_move_sound_to_tab(self, button, source_grid, child_widget, dest_grid, main_popover):
        main_popover.popdown()
        sound_btn = child_widget.get_child()
        file_path, file_name = sound_btn.file_path, sound_btn.file_name
        is_playing = file_path in self.active_sounds
        source_grid.remove(child_widget)
        self.add_sound_card_to_grid(dest_grid, file_path, file_name)
        if is_playing:
            new_btn = self.find_button_by_path_anywhere(file_path)
            if new_btn: new_btn.remove_css_class("suggested-action"); new_btn.add_css_class("destructive-action")
        self.save_current_order_to_store()

    def on_rename_sound_clicked(self, button, sound_btn, popover):
        popover.popdown()
        dialog = Adw.MessageDialog(transient_for=self, heading="Rename Track")
        dialog.add_response("cancel", "Cancel"); dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        entry = Gtk.Entry()
        entry.set_text(sound_btn.file_name)
        dialog.set_extra_child(entry)
        entry.connect("activate", lambda e: dialog.response("save"))
        def on_dialog_response(dialog, response_id):
            if response_id == "save":
                new_name = entry.get_text().strip()
                if new_name:
                    sound_btn.file_name = new_name
                    short_name = new_name if len(new_name) <= 18 else new_name[:15] + "..."
                    sound_btn.set_label(short_name)
                    self.save_current_order_to_store()
            dialog.destroy()
        dialog.connect("response", on_dialog_response)
        dialog.present()

    def on_delete_sound_confirmed(self, button, grid, child_widget, file_path, popover):
        popover.popdown()
        proc = self.active_sounds.pop(file_path, None)
        if proc:
            try: proc.terminate()
            except Exception: pass
        grid.remove(child_widget)
        self.save_current_order_to_store()
        self.update_action_button_state()

    def on_create_tab_clicked(self, button):
        dialog = Adw.MessageDialog(transient_for=self, heading="Create New Tab")
        dialog.add_response("cancel", "Cancel"); dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        entry = Gtk.Entry()
        dialog.set_extra_child(entry)
        entry.connect("activate", lambda e: dialog.response("create"))
        def on_dialog_response(dialog, response_id):
            if response_id == "create":
                tab_name = entry.get_text().strip() or f"Tab {self.notebook.get_n_pages() + 1}"
                new_page = self.create_tab_page(tab_name)
                self.notebook.set_current_page(self.notebook.page_num(new_page))
                self.save_current_order_to_store()
            dialog.destroy()
        dialog.connect("response", on_dialog_response)
        dialog.present()

    def on_tab_right_click(self, gesture, n_press, x, y, page_scroller):
        popover = Gtk.Popover()
        popover.set_parent(gesture.get_widget())
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rename_tab_btn = Gtk.Button(label="Rename Tab"); rename_tab_btn.add_css_class("flat")
        rename_tab_btn.connect("clicked", self.on_rename_tab_clicked, page_scroller, popover)
        delete_tab_btn = Gtk.Button(label="Delete Tab"); delete_tab_btn.add_css_class("destructive-action")
        delete_tab_btn.connect("clicked", self.on_delete_tab_clicked, page_scroller, popover)
        menu_box.append(rename_tab_btn); menu_box.append(delete_tab_btn)
        popover.set_child(menu_box)
        popover.popup()

    def on_rename_tab_clicked(self, button, page_scroller, popover):
        popover.popdown()
        dialog = Adw.MessageDialog(transient_for=self, heading="Rename Tab")
        dialog.add_response("cancel", "Cancel"); dialog.add_response("save", "Save")
        entry = Gtk.Entry()
        entry.set_text(page_scroller.tab_label_text.get_text())
        dialog.set_extra_child(entry)
        def on_dialog_response(dialog, response_id):
            if response_id == "save":
                new_tab_title = entry.get_text().strip()
                if new_tab_title: page_scroller.tab_label_text.set_text(new_tab_title); self.save_current_order_to_store()
            dialog.destroy()
        dialog.connect("response", on_dialog_response)
        dialog.present()

    def on_delete_tab_clicked(self, button, page_scroller, popover):
        popover.popdown()
        if self.notebook.get_n_pages() <= 1: return
        grid = page_scroller.sound_grid
        child = grid.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.FlowBoxChild):
                btn = child.get_child()
                if btn and hasattr(btn, "file_path"):
                    proc = self.active_sounds.pop(btn.file_path, None)
                    if proc:
                        try: proc.terminate()
                        except Exception: pass
            child = child.get_next_sibling()
        self.notebook.remove_page(self.notebook.page_num(page_scroller))
        self.save_current_order_to_store()
        self.update_action_button_state()

    def on_settings_clicked(self, button):
        dialog = Adw.MessageDialog(transient_for=self, heading="Bonkboard Settings")
        dialog.add_response("close", "Close"); dialog.add_response("change", "Move Database Folder...")
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        path_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        path_lbl = Gtk.Label(label=self.store_file)
        path_lbl.add_css_class("caption"); path_lbl.set_wrap(True)
        path_box.append(Gtk.Label(label="Storage Target Database Location:"))
        path_box.append(path_lbl)
        settings_box.append(path_box)
        dialog.set_extra_child(settings_box)
        def on_settings_response(dialog, response_id):
            dialog.destroy()
            if response_id == "change": self.prompt_new_database_directory()
        dialog.connect("response", on_settings_response)
        dialog.present()

    def prompt_new_database_directory(self):
        folder_dialog = Gtk.FileDialog()
        folder_dialog.select_folder(self, None, self.on_new_directory_picked)

    def on_new_directory_picked(self, dialog, result):
        try:
            folder_info = dialog.select_folder_finish(result)
            if folder_info:
                new_store_path = os.path.join(folder_info.get_path(), "bonkboard_store.json")
                if os.path.exists(self.store_file) and self.store_file != new_store_path:
                    try: shutil.copy2(self.store_file, new_store_path)
                    except Exception: pass
                self.store_file = new_store_path
                with open(self.path_pointer_file, "w") as f: f.write(new_store_path)
                self.load_stored_sounds()
        except Exception: pass

    def find_button_by_path_anywhere(self, file_path):
        for i in range(self.notebook.get_n_pages()):
            page = self.notebook.get_nth_page(i)
            child = page.sound_grid.get_first_child()
            while child is not None:
                if isinstance(child, Gtk.FlowBoxChild):
                    btn = child.get_child()
                    if btn and getattr(btn, "file_path", "") == file_path: return btn
                child = child.get_next_sibling()
        return None

    def on_toggle_sound(self, file_path):
        btn = self.find_button_by_path_anywhere(file_path)
        if file_path in self.active_sounds:
            proc = self.active_sounds.pop(file_path, None)
            if proc:
                try: proc.terminate(); proc.wait()
                except Exception: pass
            if btn: btn.remove_css_class("destructive-action"); btn.add_css_class("suggested-action")
            self.update_action_button_state()
            return
        try:
            env = os.environ.copy()
            env["PULSE_SINK"] = "BonkboardSink"
            env["PIPEWIRE_NODE"] = "BonkboardSink"
            proc = subprocess.Popen(["mpv", "--no-video", file_path], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.active_sounds[file_path] = proc
            if btn: btn.remove_css_class("suggested-action"); btn.add_css_class("destructive-action")
            self.update_action_button_state()

            def check_alive():
                if file_path not in self.active_sounds: return False
                if proc.poll() is not None:
                    self.active_sounds.pop(file_path, None)
                    if btn: btn.remove_css_class("destructive-action"); btn.add_css_class("suggested-action")
                    self.update_action_button_state()
                    return False
                return True
            GLib.timeout_add(500, check_alive)
        except Exception as e:
            print(f"Failed to play track: {e}")


class Application(Adw.Application):
    def __init__(self): super().__init__(application_id="io.github.ake6ck.Bonkboard")
    def do_activate(self): BonkboardWindow(self).present()


Adw.init()
app = Application()
app.run()