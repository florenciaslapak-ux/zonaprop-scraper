# ZonaProp → Ficha Limpia

Genera una página HTML con fotos, descripción y características de una propiedad de ZonaProp, **sin** datos de contacto con la inmobiliaria.

---

## Instalación (solo la primera vez)

### Paso 1 — Instalar Python

1. Abrí https://www.python.org/downloads/
2. Descargá la última versión (botón amarillo grande)
3. Ejecutá el instalador
4. ⚠️ **IMPORTANTE:** marcá la casilla "Add Python to PATH" antes de hacer clic en Install Now
5. Finalizá la instalación

### Paso 2 — Instalar las dependencias

- **Windows:** hacé doble clic en `1_instalar.bat`
- **Mac/Linux:** abrí una terminal en esta carpeta y ejecutá:
  ```
  pip install -r requirements.txt
  ```

---

## Uso

### Windows
Hacé doble clic en `2_iniciar.bat`. Se abrirá el navegador automáticamente.

### Mac / Linux
```bash
python server.py
```
Luego abrí http://localhost:5000 en tu navegador.

---

## Cómo usarlo

1. Copiá el link de una propiedad de ZonaProp (ej: `https://www.zonaprop.com.ar/propiedades/...`)
2. Pegalo en el campo de la app
3. Hacé clic en **Generar ficha**
4. Esperá unos segundos
5. Descargá el archivo HTML o usá la vista previa

---

## Notas

- ZonaProp a veces bloquea solicitudes automáticas. Si falla, esperá unos segundos y volvé a intentar.
- El archivo HTML generado incluye las imágenes directamente desde ZonaProp (requiere conexión a internet para verlas).
- No se almacena ningún dato.

---

## Estructura del proyecto

```
zonaprop-scraper/
├── server.py          ← servidor principal
├── requirements.txt   ← dependencias Python
├── templates/
│   └── index.html     ← interfaz web
├── 1_instalar.bat     ← instalador (Windows)
└── 2_iniciar.bat      ← iniciador (Windows)
```
