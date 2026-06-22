import requests
from bs4 import BeautifulSoup
from google import genai
import os
import time
import random

# --- 1. CONFIGURACIÓN DE LA IA ---
API_KEY = os.environ.get("LLAVESECRETABRAI")
client = genai.Client(api_key=API_KEY)

# --- 2. EL RECOLECTOR MULTI-FUENTE ---
# Agregamos las páginas que querías leer
fuentes = [
    {"nombre": "ÁMBITO", "url": "https://www.ambito.com/", "base": "https://www.ambito.com"},
    {"nombre": "INFOBAE", "url": "https://www.infobae.com/", "base": "https://www.infobae.com"},
    {"nombre": "TN", "url": "https://tn.com.ar/", "base": "https://tn.com.ar"},
    {"nombre": "OLÉ", "url": "https://www.ole.com.ar/", "base": "https://www.ole.com.ar"}
]

encabezados = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
noticias_extraidas = []

print("Extrayendo noticias de múltiples fuentes...")
for fuente in fuentes:
    try:
        respuesta = requests.get(fuente["url"], headers=encabezados, timeout=10)
        if respuesta.status_code == 200:
            sopa = BeautifulSoup(respuesta.text, 'html.parser')
            # Buscamos etiquetas h2 y h1 (donde los diarios suelen poner sus títulos)
            articulos = sopa.find_all(['h2', 'h1']) 
            contador = 0
            
            for articulo in articulos:
                texto_limpio = articulo.text.strip()
                enlace_tag = articulo.find('a')
                
                if enlace_tag and 'href' in enlace_tag.attrs:
                    link = enlace_tag['href']
                    if not link.startswith('http'):
                        link = fuente["base"] + link
                    
                    # Filtramos títulos muy cortos que suelen ser basura
                    if len(texto_limpio) > 25: 
                        noticias_extraidas.append({"fuente": fuente["nombre"], "titulo": texto_limpio, "link": link})
                        contador += 1
                        if contador >= 2: # Tomamos 2 noticias de cada diario para mezclar
                            break
    except Exception as e:
        print(f"No se pudo leer {fuente['nombre']}: {e}")

# Mezclamos las noticias para que quede variado y elegimos 6
random.shuffle(noticias_extraidas)
noticias_finales = noticias_extraidas[:6]

texto_para_ia = ""
for i, noticia in enumerate(noticias_finales):
    texto_para_ia += f"Noticia {i+1} [{noticia['fuente']}]:\n- Título: {noticia['titulo']}\n- Link: {noticia['link']}\n\n"

# --- 3. EL CEREBRO (Ahora con resúmenes largos) ---
prompt = f"""
Eres un editor experto de noticias. Aquí tienes 6 noticias reales de hoy de distintos medios:
{texto_para_ia}

Devuelve ESTRICTAMENTE la información en este formato por cada noticia, separando con el símbolo |.
Clasifica obligatoriamente cada noticia en UNA de estas categorías: DEPORTES, SOCIEDAD, POLÍTICA, ECONOMÍA, TECNOLOGÍA.
Redacta un RESUMEN EXTENDIDO detallado de entre 3 y 4 oraciones (no hagas resúmenes cortos).

Formato exacto (5 elementos):
DIARIO|CATEGORIA|TÍTULO REFORMULADO|RESUMEN EXTENDIDO|LINK
"""

max_intentos = 3
exito = False

for intento in range(max_intentos):
    try:
        print(f"Intento {intento + 1} de conectar con la IA...")
        respuesta_ia = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        exito = True
        break
    except Exception as e:
        print(f"Fallo en el intento {intento + 1}: {e}")
        if intento < max_intentos - 1:
            time.sleep(15)
        else:
            try:
                respuesta_ia = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                exito = True
            except Exception as error_respaldo:
                print("Fallaron todos los modelos.", error_respaldo)

if exito:
    # --- 4. ENSAMBLADOR WEB CON JAVASCRIPT ---
    lineas = respuesta_ia.text.strip().split('\n')
    tarjetas_html = ""
    
    for linea in lineas:
        if "|" in linea:
            partes = linea.split("|")
            if len(partes) >= 5: # Ahora esperamos 5 partes (incluye la fuente)
                fuente_diario = partes[0].strip().upper()
                categoria = partes[1].strip().upper()
                titulo = partes[2].strip()
                resumen = partes[3].strip()
                link = partes[4].strip()
                
                # Colores
                if categoria == "DEPORTES":
                    borde = "border-emerald-500"
                    pill = "bg-emerald-900/40 text-emerald-400"
                elif categoria == "SOCIEDAD":
                    borde = "border-purple-500"
                    pill = "bg-purple-900/40 text-purple-400"
                elif categoria == "ECONOMÍA" or categoria == "POLÍTICA":
                    borde = "border-blue-500"
                    pill = "bg-blue-900/40 text-blue-400"
                elif categoria == "TECNOLOGÍA":
                    borde = "border-pink-500"
                    pill = "bg-pink-900/40 text-pink-400"
                else:
                    borde = "border-gray-500"
                    pill = "bg-gray-800 text-gray-300"
                
                # Atributo data-categoria para que el Javascript pueda filtrarlo
                tarjetas_html += f"""
                <article data-categoria="{categoria}" class="tarjeta-noticia bg-[#111827] rounded-xl p-6 flex flex-col border-l-4 {borde} hover:scale-[1.02] transition-transform duration-300 shadow-lg">
                    <div class="flex justify-between items-center mb-4 text-xs font-bold tracking-wide">
                        <div class="flex gap-2">
                            <span class="bg-gray-800 text-white px-2.5 py-1 rounded-md border border-gray-700">{fuente_diario}</span>
                            <span class="{pill} px-2.5 py-1 rounded-md">{categoria}</span>
                        </div>
                    </div>
                    <h2 class="text-xl font-bold text-white mb-3 leading-tight">{titulo}</h2>
                    <p class="text-gray-400 text-sm mb-6 flex-grow leading-relaxed">{resumen}</p>
                    <a href="{link}" target="_blank" class="text-white text-sm font-semibold hover:underline flex justify-start items-center gap-1 mt-auto">
                        Leer nota completa &rarr;
                    </a>
                </article>
                """
    
    html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Noticias IA</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body {{ background-color: #0b0f19; font-family: 'Inter', sans-serif; }}</style>
</head>
<body class="text-gray-300 antialiased min-h-screen pb-12">
    
    <nav class="flex justify-between items-center px-8 py-5 border-b border-gray-800 bg-[#0b0f19]">
        <div class="text-2xl font-black text-white flex items-center gap-2">Noticias IA 🤖</div>
    </nav>
    
    <header class="text-center mt-16 mb-12 px-4">
        <h1 class="text-4xl md:text-5xl font-black text-white mb-6 tracking-tight">
            La información al <span class="text-transparent bg-clip-text bg-gradient-to-r from-yellow-400 to-orange-500">instante</span>
        </h1>
        <p class="text-gray-400 max-w-2xl mx-auto text-lg">Las noticias más relevantes de Argentina leídas, categorizadas y resumidas a fondo por Inteligencia Artificial.</p>
    </header>

    <div class="max-w-4xl mx-auto px-4 flex flex-wrap justify-center gap-3 mb-12">
        <button data-filter="TODAS" class="btn-filtro bg-gradient-to-r from-yellow-400 to-orange-500 text-black px-5 py-2.5 rounded-full font-bold text-sm shadow-lg shadow-orange-500/20 transition">Todas</button>
        <button data-filter="POLÍTICA" class="btn-filtro bg-[#1f2937] text-gray-300 px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-gray-700 transition">Política</button>
        <button data-filter="ECONOMÍA" class="btn-filtro bg-[#1f2937] text-gray-300 px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-gray-700 transition">Economía</button>
        <button data-filter="DEPORTES" class="btn-filtro bg-[#1f2937] text-gray-300 px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-gray-700 transition">Deportes</button>
        <button data-filter="SOCIEDAD" class="btn-filtro bg-[#1f2937] text-gray-300 px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-gray-700 transition">Sociedad</button>
        <button data-filter="TECNOLOGÍA" class="btn-filtro bg-[#1f2937] text-gray-300 px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-gray-700 transition">Tecnología</button>
    </div>

    <main class="max-w-6xl mx-auto px-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tarjetas_html}
    </main>

    <script>
        const botones = document.querySelectorAll('.btn-filtro');
        const articulos = document.querySelectorAll('.tarjeta-noticia');

        botones.forEach(boton => {{
            boton.addEventListener('click', () => {{
                // 1. Apagamos todos los botones
                botones.forEach(b => {{
                    b.className = 'btn-filtro bg-[#1f2937] text-gray-300 px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-gray-700 transition';
                }});

                // 2. Encendemos solo el botón clickeado
                boton.className = 'btn-filtro bg-gradient-to-r from-yellow-400 to-orange-500 text-black px-5 py-2.5 rounded-full font-bold text-sm shadow-lg shadow-orange-500/20 transition';

                // 3. Mostramos u ocultamos las tarjetas según la categoría
                const categoriaElegida = boton.getAttribute('data-filter');
                
                articulos.forEach(art => {{
                    if (categoriaElegida === 'TODAS' || art.getAttribute('data-categoria') === categoriaElegida) {{
                        art.style.display = 'flex';
                    }} else {{
                        art.style.display = 'none';
                    }}
                }});
            }});
        }});
    </script>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as archivo:
        archivo.write(html_completo)
        
    print("¡Éxito! Web actualizada con múltiples diarios, JS para botones y resúmenes largos.")

else:
    print("Error crítico en la conexión.")
