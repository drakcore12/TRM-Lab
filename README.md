# TRM Lab · Distribución del dólar en Colombia

Dashboard universitario en HTML + Python con **gráficos de cajas interactivos** y **gráficos Seaborn generados en el servidor**.

## Fuente y actualización

Fuente primaria: Superintendencia Financiera de Colombia, por medio del conjunto **Tasa de Cambio Representativa del Mercado- TRM**, ID `32sa-8pi3` del Portal Nacional de Datos Abiertos.

- Vista: https://www.datos.gov.co/Econom-a-y-Finanzas/Tasa-de-Cambio-Representativa-del-Mercado-TRM/32sa-8pi3
- API: https://www.datos.gov.co/resource/32sa-8pi3.json
- Campos: `valor`, `unidad`, `vigenciadesde`, `vigenciahasta`.
- Consulta automática desde 2020; se renueva cada 20 minutos y al pulsar «Actualizar datos».
- *Importante*: la **TRM oficial es diaria**, no un precio del mercado spot en segundos. La aplicación informa la última fecha de vigencia disponible y la fecha de consulta.
- Si falla la API, utiliza datos ya guardados y avisa que están desactualizados; si no hay datos, muestra un mensaje, **nunca inventa cotizaciones**.
- Cada registro se considera una fecha de comienzo de vigencia; no se rellena el fin de semana con observaciones artificiales.

## Funcionalidades

- Gráfico principal de cajas (Plotly) por mes, trimestre y año, con valores atípicos.
- Diagrama de cajas auténtico (Seaborn+Matplotlib), generado dinámicamente por Python al filtrar.
- Gráfico temporal de la tasa de cambio y heatmap de promedios mensuales.
- Indicadores de TRM vigente, variación respecto del registro anterior, media, mediana, mínimo, máximo, cuartiles, IQR, desviación estándar y outliers.
- Periodos rápidos 6 meses, 1 año, 2 años, 5 años y fechas personalizadas.
- Exportación CSV de datos reales del periodo y PNG del gráfico de cajas.
- Dashboard responsive (computador, tablet, celular), navegación por teclado y aviso de errores.
- Conexión directa a la API REST oficial; **no** utiliza base de datos MySQL/PostgreSQL, porque la actividad no lo exige.

## Ejecutar en tu computador

**Requisitos:** Python 3.11+, conexión a internet para descargar dependencias y consultar datos, librerías de `requirements.txt`.

```bash
python -m pip install -r requirements.txt
python app.py
```

Abrir `http://localhost:10000`. **No** abrir `static/index.html` directamente: debe ejecutarse el servidor para que funcionen los gráficos y las consultas.

## Publicar gratis en Render

1. Crear un repositorio GitHub y subir **todos** los archivos del proyecto (Plotly se carga desde el CDN público).
2. En Render: **New > Blueprint** y seleccionar el repositorio: `render.yaml` ya define servidor Python, instalación y comando de inicio.
3. Una vez terminado el despliegue, abrir la URL `https://...onrender.com` y verificar que cargan gráficos.
4. En Google Classroom entregar el enlace **del servicio Render**, no de GitHub. Como soporte opcional adjuntar `Codigo_Python_TRM.txt`.

También puedes crear un **Web Service** manual con build `pip install -r requirements.txt`, start `python app.py`, plan Free, `PYTHON_VERSION=3.11.11`.

**Nota:** el plan gratis de Render puede suspenderse por inactividad y tardar en iniciar. Render debe tener salida de Internet para consultar la API.

## Endpoints

- `/api/health` — estado del servidor.
- `/api/trm?start=2025-01-01&end=2025-12-31&group=month` — JSON de datos/estadísticas/grupos.
- `/api/seaborn.png?start=2025-01-01&end=2025-12-31&group=month` — gráfico real de Seaborn.
- `/api/export.csv?...` — CSV con los registros oficiales filtrados.

`group` acepta `month`, `quarter`, `year`; `refresh=1` solicita actualizar la API en ese instante.

## Criterios del trabajo

| Criterio | Implementación |
|---|---|
| Box plot | 2 enfoques: Plotly interactivo y Seaborn servidor |
| Precio USD/COP | TRM oficial de Superfinanciera |
| Personalización | Fechas, agrupación, tooltips, descarga y diseño |
| Accesibilidad | Interfaz móvil, etiquetas, foco visible, lectura y contraste |
| Accesible a cualquier usuario | Despliegue público requerido en Render |
| Datos en tiempo real | Reconsulta periódica del último dato oficial disponible (publicación diaria; no spot intradía) |

## Integridad académica

No se simulan tasas de cambio en la aplicación. Cada cálculo se hace con valores entregados por la fuente oficial. El método de detección global de outliers es 1,5 × IQR; Plotly/Seaborn aplican sus whiskers a cada caja individual.
