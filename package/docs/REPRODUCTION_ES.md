# Reproducción local y en contenedor

## Archivos, carpetas y requisitos

La distribución 0.1.2 se entrega como un ZIP y un bundle Docker externo. Verifica ambos con Get-FileHash antes de instalar; contrasta los resultados con SHA256SUMS.txt. Un checksum acredita integridad respecto de ese registro, no autoría.

Windows requiere arquitectura AMD64, CPython 3.12 y el lanzador py accesible mediante py -3.12. El cálculo no requiere TeX ni Poppler. Usa una extracción, un entorno y destinos de corrida nuevos.

## Secuencia Windows

Desde la raíz recién extraída:

~~~powershell
Remove-Item Env:PYTHONPATH,Env:PYTHONHOME,Env:BOOK_REPRO_ROOT -ErrorAction SilentlyContinue
py -3.12 --version
.\bootstrap_windows.ps1 -VenvPath .venv-0.1.2
$env:BOOK_REPRO_OFFLINE = "1"
$env:BOOK_REPRO_ROOT = (Get-Location).Path
$python = ".\.venv-0.1.2\Scripts\python.exe"
& $python -m book_repro verify-package --archive PATH_TO_DELIVERED_ZIP
& $python -m book_repro check-env
& $python -m book_repro reproduce --output build\windows-run
& $python -m book_repro verify --run build\windows-run
& $python -m book_repro coverage --output build\coverage-structural.json
~~~

El bootstrap instala sólo desde vendor/wheels y exige los hashes de locks/requirements-windows.txt. BOOK_REPRO_OFFLINE activa una guardia de sockets durante los comandos; no modifica el cortafuegos del anfitrión. reproduce ya ejecuta la suite obligatoria. test es un diagnóstico opcional.

Las rutas results/ e independent/ son relativas al destino de --output: en este ejemplo quedan en build/windows-run/results y build/windows-run/independent.

## Secuencia Linux AMD64 con el bundle

Se requiere un motor Docker para contenedores Linux; el nombre concreto del contexto depende de la instalación. Carga primero el bundle entregado y consulta ENVIRONMENT_MANIFEST.json, situado junto al bundle, para cotejar etiquetas, IDs, digests y plataforma:

~~~powershell
docker load --input PATH_TO_DELIVERED_DOCKER_BUNDLE
docker image inspect book-repro-runtime:0.1.2
docker image inspect book-repro-docs:0.1.2
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-runtime:0.1.2 `
  python -m book_repro reproduce --output /work/build/linux-run
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-runtime:0.1.2 `
  python -m book_repro verify --run /work/build/linux-run
~~~

La fuente extraída se monta en /work. Por tanto, /work/build es la carpeta build del anfitrión. Esta modalidad ejecuta la fuente montada. Ejecutar la copia incorporada en la imagen es una modalidad diagnóstica distinta y no forma parte del recorrido principal.

Como alternativa se pueden reconstruir las imágenes:

~~~powershell
docker build --platform linux/amd64 --target runtime -t book-repro-runtime:0.1.2 .
docker build --platform linux/amd64 --target docs -t book-repro-docs:0.1.2 .
~~~

La reconstrucción puede requerir red para paquetes Debian. Una vez preparado el entorno, las órdenes científicas anteriores usan --network none y la guardia Python.

## Comparación entre plataformas

Tras producir las dos corridas nuevas:

~~~powershell
& $python -m book_repro compare-runs --windows build\windows-run --linux build\linux-run --output build\platform-comparison.json
~~~

La comparación histórica mediante --baseline es opcional y sólo procede si el receptor recibe por separado una corrida histórica identificada. No se incluye ni se necesita para comparar Windows y Linux.

## Construcción e inspección del PDF

La ruta recomendada no exige TeX nativo:

~~~powershell
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  python -m book_repro build-docs --run /work/build/linux-run --output /work/build/linux-docs
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  pdfinfo /work/build/linux-docs/example_EN.pdf
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  pdftoppm -png -r 144 /work/build/linux-docs/example_EN.pdf /work/build/linux-docs/page
~~~

El PDF queda en build/linux-docs/example_EN.pdf; el informe, en build/linux-docs/build_docs_report.json. Inspecciona todas las páginas renderizadas. La alternativa nativa requiere latexmk, pdflatex y pdfinfo en PATH; pdftoppm se usa para la inspección.

## Manuscrito opcional

La cobertura estructural anterior funciona sin el libro. Sólo si se suministra por separado una copia identificada de v22:

~~~powershell
& $python -m book_repro coverage --manuscript PATH_TO_IDENTIFIED_V22_COPY --output build\coverage-with-manuscript.json
& $python -m book_repro check-book --manuscript PATH_TO_IDENTIFIED_V22_COPY --run build\windows-run --output build\book-check.json
~~~

Estas órdenes comprueban hash, etiquetas, rangos y correspondencias; no rederivan los 82 resultados. La ausencia del manuscrito no constituye un fallo del ejemplo autónomo.

## Fallos frecuentes

- El destino ya existe: elige otro; una corrida sellada no se sobrescribe.
- py -3.12 no responde: instala o selecciona CPython 3.12 antes de crear el entorno.
- Falla un wheel o su hash: restaura el archivo entregado; no desactives --require-hashes.
- Docker no ejecuta Linux: selecciona en tu instalación un motor compatible con contenedores Linux.
- build-docs no encuentra TeX/Poppler: usa la imagen documental o instala las herramientas sólo para la capa documental.
- Un resultado científico difiere: conserva ambas corridas y documenta la discrepancia; no cambies referencias ni tolerancias.
