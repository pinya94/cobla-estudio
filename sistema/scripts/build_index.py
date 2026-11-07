"""Build the site home page (password gate + piece list): python3 build_index.py <site_dir> <password>"""
import json, os, sys, glob, hashlib, html

site, pw = sys.argv[1], sys.argv[2]
h = hashlib.sha256(("cpm:" + pw).encode()).hexdigest()
metas = sorted((json.load(open(f)) for f in glob.glob(f"{site}/*/meta.json")), key=lambda m: m["title"])
cards = "\n".join(f'''<a class="piece" href="{m["slug"]}/index.html">
  <b>{html.escape(m["title"])}</b>
  <span>{html.escape(m.get("subtitle", ""))}</span>
  <small>{html.escape(" · ".join(m["voices"]))}</small>
  {f'<em>{html.escape(m["notes"])}</em>' if m.get("notes") else ""}
</a>''' for m in metas)
page = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cobla Pro Music · Estudio</title>
<style>
:root{{--bg:#f6f3ee;--card:#fff;--ink:#1f1d1a;--mute:#6f6a62;--line:#e4ded4;--acc:#b5462b}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding:28px 18px}}
h1{{margin:0 0 4px;font-size:26px}} .sub{{color:var(--mute);margin:0 0 22px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}}
.piece{{display:flex;flex-direction:column;gap:4px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;text-decoration:none;color:inherit}}
.piece:hover{{border-color:var(--acc);box-shadow:0 0 0 2px #b5462b22}}
.piece b{{font-size:17px}} .piece span{{color:var(--mute);font-size:14px}} .piece small{{color:var(--mute);font-size:12.5px}} .piece em{{font-size:12.5px;color:#8a5a00}}
.gate{{max-width:360px;margin:12vh auto;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px}}
input{{font:inherit;width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:10px;margin:10px 0}}
button{{font:inherit;width:100%;padding:11px;border-radius:10px;border:none;background:var(--acc);color:#fff;font-weight:600;cursor:pointer}}
.err{{color:#c33;font-size:14px;min-height:20px}}
.help{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-top:22px;font-size:14px;color:var(--mute)}}
</style></head><body>
<div id="gate" class="gate" style="display:none">
  <h2 style="margin-top:0">Cobla Pro Music 🎶</h2>
  <p class="sub" style="margin:0">Estudio de partituras del grupo</p>
  <form id="f"><input id="pw" type="password" placeholder="Contraseña del grupo" autocomplete="current-password"><button>Entrar</button></form>
  <div class="err" id="err"></div>
</div>
<div id="home" class="wrap" style="display:none">
  <h1>Cobla Pro Music 🎶</h1>
  <p class="sub">Elige una pieza, elige tu voz y estudia por fases. Usa auriculares cuando la app te escuche por el micro.</p>
  <div class="grid">{cards}</div>
  <div class="help"><b>Cómo funciona:</b> 1 · escuchas tu voz → 2 · la tocas tú solo y lento (la app te corrige) → 3 · con la base → 4 · con tus compañeros → 5 · con todo el grupo menos tú. Toca un compás de la partitura para repetir ese trozo en bucle. Cada pieza tiene tu PDF anotado (con quién vas, entradas y pasajes difíciles).<br><br>
  Las partituras se han convertido automáticamente desde los PDF: si ves algún compás raro, avisa.</div>
</div>
<script>
const H="{h}";
async function sha(t){{ const b=await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)); return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join(""); }}
function ok(){{ try{{ return localStorage.getItem("cpm_ok")==="1" && localStorage.getItem("cpm_h")===H; }}catch(e){{ return false; }} }}
function show(){{ const o=ok(); document.getElementById("gate").style.display=o?"none":""; document.getElementById("home").style.display=o?"":"none"; }}
document.getElementById("f").onsubmit=async e=>{{ e.preventDefault(); const v=document.getElementById("pw").value.trim();
  if(await sha("cpm:"+v)===H){{ try{{ localStorage.setItem("cpm_ok","1"); localStorage.setItem("cpm_h",H); }}catch(e){{}} show(); }}
  else document.getElementById("err").textContent="Contraseña incorrecta"; }};
show();
</script>
</body></html>'''
open(f"{site}/index.html", "w").write(page)
open(f"{site}/.nojekyll", "w").write("")
print("index ok:", len(metas), "piezas")
