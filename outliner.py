# file: outliner_app.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import xml.etree.ElementTree as ET
import requests
from base64 import b64encode

WEBDAV_URL = "WebDAV_URL"
WEBDAV_USER = "demo"
WEBDAV_PASS = "12345678"

class OutlinerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Outliner")
        self.root.geometry("800x600")
        self.root.minsize(400, 300)

        self.clipboard = None

        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)
        file_menu = tk.Menu(self.menu, tearoff=0)
        file_menu.add_command(label="Save to WebDAV", command=self.export_md_webdav)
        file_menu.add_command(label="Load from WebDAV", command=self.import_md_webdav)
        self.menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(self.menu, tearoff=0)
        edit_menu.add_command(label="Add Item", command=self.add_item)
        edit_menu.add_command(label="Delete Item", command=self.delete_item)
        edit_menu.add_command(label="Edit Item", command=self.edit_item)
        edit_menu.add_command(label="Indent Item", command=self.indent_item)
        edit_menu.add_command(label="Outdent Item", command=self.outdent_item)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copy Item", command=self.copy_item)
        edit_menu.add_command(label="Paste Item", command=self.paste_item)
        self.menu.add_cascade(label="Edit", menu=edit_menu)

        self.toolbar = tk.Frame(root)
        self.toolbar.pack(fill=tk.X)

        tk.Button(self.toolbar, text="Add", command=self.add_item).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="Delete", command=self.delete_item).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="Edit", command=self.edit_item).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="Indent", command=self.indent_item).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="Outdent", command=self.outdent_item).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="Save WebDAV", command=self.export_md_webdav).pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="Load WebDAV", command=self.import_md_webdav).pack(side=tk.LEFT)

        tree_frame = tk.Frame(root)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, show="tree")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.status = tk.Label(root, text="Ready", anchor="w")
        self.status.pack(fill=tk.X)

        self.tree.tag_configure('highlight', background='#d0ebff')

        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_release)
        self.tree.bind("<Double-1>", self.edit_item)

        self.dragging = None
        self.last_highlight = None

    def set_status(self, msg):
        self.status.config(text=msg)

    def add_item(self):
        selected = self.tree.focus()
        parent = selected if selected else ""
        depth = self.get_depth(parent)
        if depth >= 4:
            messagebox.showwarning("Max Depth", "Cannot indent beyond 4 levels.")
            return
        self.tree.insert(parent, "end", text="New Item")

    def delete_item(self):
        selected = self.tree.focus()
        if selected:
            self.tree.delete(selected)

    def edit_item(self, event=None):
        selected = self.tree.focus()
        if selected:
            current_text = self.tree.item(selected, "text")
            new_text = simpledialog.askstring("Edit Item", "Edit text:", initialvalue=current_text)
            if new_text is not None:
                self.tree.item(selected, text=new_text)

    def indent_item(self):
        item = self.tree.focus()
        prev = self.tree.prev(item)
        if not prev:
            return
        depth = self.get_depth(prev)
        if depth + 1 > 4:
            messagebox.showwarning("Max Depth", "Cannot indent beyond 4 levels.")
            return
        self.tree.move(item, prev, "end")

    def outdent_item(self):
        item = self.tree.focus()
        parent = self.tree.parent(item)
        grandparent = self.tree.parent(parent)
        if parent:
            self.tree.move(item, grandparent, self.tree.index(parent) + 1)

    def get_depth(self, item):
        depth = 0
        while item:
            item = self.tree.parent(item)
            depth += 1
        return depth

    def on_drag_start(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.dragging = iid

    def on_drag_motion(self, event):
        target = self.tree.identify_row(event.y)
        if target and target != self.dragging:
            if self.last_highlight and self.tree.exists(self.last_highlight):
                self.tree.item(self.last_highlight, tags='')
            self.tree.item(target, tags=('highlight',))
            self.last_highlight = target

    def on_drag_release(self, event):
        if not self.dragging:
            return
        target = self.tree.identify_row(event.y)
        if self.last_highlight and self.tree.exists(self.last_highlight):
            self.tree.item(self.last_highlight, tags='')
        if target and target != self.dragging:
            parent = self.tree.parent(target)
            index = self.tree.index(target)
            self.tree.move(self.dragging, parent, index)
        self.dragging = None
        self.last_highlight = None

    def copy_item(self):
        selected = self.tree.focus()
        if selected:
            self.clipboard = self.copy_tree_recursive(selected)

    def paste_item(self):
        if self.clipboard:
            selected = self.tree.focus()
            parent = selected if selected else ""
            self.paste_tree_recursive(self.clipboard, parent)

    def copy_tree_recursive(self, item):
        text = self.tree.item(item, "text")
        children = [self.copy_tree_recursive(child) for child in self.tree.get_children(item)]
        return {"text": text, "children": children}

    def paste_tree_recursive(self, data, parent):
        new_item = self.tree.insert(parent, "end", text=data["text"])
        for child in data["children"]:
            self.paste_tree_recursive(child, new_item)

    def export_md_webdav(self):
        lines = []
        self.write_md(self.tree.get_children(), lines, 1)
        content = '\n'.join(lines)
        try:
            response = requests.put(
                WEBDAV_URL,
                headers={
                    "Authorization": "Basic " + b64encode(f"{WEBDAV_USER}:{WEBDAV_PASS}".encode()).decode()
                },
                data=content.encode("utf-8")
            )
            if response.ok:
                self.set_status("Saved to WebDAV ✅")
            else:
                self.set_status(f"Failed to save: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def import_md_webdav(self):
        try:
            response = requests.get(
                WEBDAV_URL,
                headers={
                    "Authorization": "Basic " + b64encode(f"{WEBDAV_USER}:{WEBDAV_PASS}".encode()).decode()
                }
            )
            if response.ok:
                lines = response.text.splitlines()
                self.tree.delete(*self.tree.get_children())
                stack = [""] * 5
                for line in lines:
                    if line.strip().startswith("#"):
                        level = line.count("#")
                        if level > 4:
                            continue
                        text = line.strip("# ")
                        parent = stack[level - 1]
                        iid = self.tree.insert(parent, "end", text=text)
                        stack[level] = iid
                self.set_status("Loaded from WebDAV ✅")
            else:
                self.set_status(f"Failed to load: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def write_md(self, items, output, level):
        for iid in items:
            text = self.tree.item(iid, "text")
            output.append("#" * level + f" {text}")
            self.write_md(self.tree.get_children(iid), output, level + 1)

if __name__ == "__main__":
    root = tk.Tk()
    app = OutlinerApp(root)
    root.mainloop()