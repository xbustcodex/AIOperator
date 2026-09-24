/* Buster GUI — Files.

All filesystem operations go through Buster's capability + permission model
(/api/files, /api/file, /api/fs -> RPC "call"). The frontend has no
unrestricted filesystem access. Permission denials are surfaced with a clear
path to approve in Permissions.
*/

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api, go } = ctx;
  clear(root);
  const path = ctx.routeState?.path || ".";
  const build = (data) => {
    clear(root);
    root.appendChild(el("h1", null, "My Files"));
    const nav = el("div", "row gap-sm");
    nav.appendChild(el("span", "small faint", "Location: " + (path || "/")));
    root.appendChild(nav);

    if (data && data.data) {
      const entries = data.data.entries || {};
      const grid = el("div", "grid2");
      const names = Object.keys(entries).sort();
      for (const name of names) {
        const kind = entries[name];
        const tile = el("button", "tile", kind === "dir" ? name + "/" : name);
        tile.setAttribute("data-kind", kind);
        tile.addEventListener("click", async () => {
          if (kind === "dir") {
            const next = path === "." ? name : [path, name].join("/");
            ctx.routeState = { path: next };
            await render(root, ctx);
          } else {
            const res = await api.get("/api/file", { path: [path === "." ? "" : path, name].join("/").replace(/^\/+/, "") });
            const detail = el("div", "card");
            detail.appendChild(el("h3", null, name));
            if (res.ok) detail.appendChild(el("pre", "small", truncate(String(res.data), 4000)));
            else detail.appendChild(el("p", "muted", res.error || "can't read file"));
            root.appendChild(detail);
          }
        });
        grid.appendChild(tile);
      }
      if (names.length === 0) grid.appendChild(el("p", "muted", "Nothing here yet."));
      root.appendChild(grid);
    } else if (data && data.error) {
      root.appendChild(el("p", "muted", data.error));
    } else if (data && data.offline) {
      root.appendChild(el("p", "muted", "My Files needs the Buster runtime. Reconnecting…"));
    }
  };

  const data = await api.get("/api/files", { path });
  build(data);
}

function truncate(text, max) {
  return text.length > max ? text.slice(0, max) + "…" : text;
}