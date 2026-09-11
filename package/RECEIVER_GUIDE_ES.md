# Guía inicial del receptor — versión 0.1.2

Esta guía reproduce el ejemplo sin conocer entregas internas anteriores. Conserva el ZIP y el bundle originales; extrae el ZIP en una carpeta nueva y ejecuta todos los bloques desde la raíz extraída.

## 1. Comprueba los archivos antes de instalar

En la carpeta que contiene los archivos entregados:

~~~powershell
Get-FileHash -Algorithm SHA256 .\automation-institutions-reproducibility-0.1.2.zip
Get-FileHash -Algorithm SHA256 .\automation-institutions-reproducibility-0.1.2-linux-amd64-images.tar.gz
Get-Content .\SHA256SUMS.txt
~~~

Compara los valores con SHA256SUMS.txt. Son controles de integridad de transporte, no una firma independiente de autoría.

## 2. Extrae e instala en Windows

Requisitos: Windows AMD64, CPython 3.12 y py -3.12. Sustituye sólo <ENTREGA> por la ruta absoluta de la carpeta que contiene los archivos:

~~~powershell
$delivery = '<ENTREGA>'
Set-Location $delivery
Expand-Archive -LiteralPath .\automation-institutions-reproducibility-0.1.2.zip -DestinationPath .\receiver-clean
Set-Location .\receiver-clean\automation-institutions-reproducibility-0.1.2
Remove-Item Env:PYTHONPATH,Env:PYTHONHOME,Env:BOOK_REPRO_ROOT -ErrorAction SilentlyContinue
py -3.12 --version
.\bootstrap_windows.ps1 -VenvPath .venv-0.1.2
$env:BOOK_REPRO_OFFLINE = '1'
$env:BOOK_REPRO_ROOT = (Get-Location).Path
$python = '.\.venv-0.1.2\Scripts\python.exe'
& $python -m book_repro verify-package --archive (Join-Path $delivery 'automation-institutions-reproducibility-0.1.2.zip')
& $python -m book_repro reproduce --output build\windows-run
& $python -m book_repro verify --run build\windows-run
& $python -m book_repro coverage --output build\coverage-structural.json
~~~

reproduce ejecuta las pruebas obligatorias. test queda disponible sólo como diagnóstico opcional. La salida numérica se guarda en build/windows-run/results; los controles independientes, en build/windows-run/independent.

## 3. Carga las imágenes y reproduce en Linux

Se necesita un motor Docker capaz de ejecutar contenedores Linux AMD64. Desde la raíz extraída:

~~~powershell
docker load --input (Join-Path $delivery 'automation-institutions-reproducibility-0.1.2-linux-amd64-images.tar.gz')
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

El montaje hace que /work/build/linux-run sea exactamente build/linux-run en el anfitrión. Docker puede reutilizar capas existentes al cargar el bundle; esto no demuestra una recuperación física desde un almacén vacío. La reconstrucción con docker build es alternativa y puede requerir red.

## 4. Compara y construye el documento

~~~powershell
& $python -m book_repro compare-runs --windows build\windows-run --linux build\linux-run --output build\platform-comparison.json
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  python -m book_repro build-docs --run /work/build/linux-run --output /work/build/linux-docs
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  pdftoppm -png -r 144 /work/build/linux-docs/example_EN.pdf /work/build/linux-docs/page
~~~

Inspecciona todas las imágenes build/linux-docs/page-*.png. El PDF está en build/linux-docs/example_EN.pdf y el informe en build/linux-docs/build_docs_report.json.

El cálculo no necesita TeX ni Poppler. Como alternativa nativa, build-docs requiere latexmk, pdflatex y pdfinfo; pdftoppm sirve para inspeccionar.

## 5. Alcance opcional del manuscrito

coverage sin --manuscript es autónomo. coverage --manuscript y check-book sólo se ejecutan si el receptor dispone por separado de la copia v22 identificada por hash. Su ausencia no es un fallo del ejemplo.

Consulta docs/REPRODUCTION_ES.md para el procedimiento detallado y docs/ENVIRONMENT_RECOVERY_ES.md para identidades de imágenes, recuperación y reconstrucción alternativa.
