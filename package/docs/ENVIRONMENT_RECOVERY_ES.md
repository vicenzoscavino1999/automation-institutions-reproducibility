# Conservación y recuperación del entorno

La versión 0.1.2 se acompaña de un bundle Docker Linux AMD64 con imágenes de cálculo y documentación. El ZIP conserva también wheels y locks para crear el entorno Windows sin consultar un índice Python.

## Identidad

- Plataforma de contenedor: linux/amd64.
- Base fijada: python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea.
- Imágenes activas: book-repro-runtime:0.1.2 y book-repro-docs:0.1.2.
- Locks: locks/requirements-linux-amd64.txt y locks/requirements-windows.txt.

Los IDs, digests, componentes y hashes efectivos están en ENVIRONMENT_MANIFEST.json, entregado junto al bundle. DEBIAN_PACKAGES.tsv registra el inventario obtenido de las imágenes efectivas.

## Recuperar el bundle

Comprueba primero el hash externo y luego carga:

~~~powershell
Get-FileHash -Algorithm SHA256 .\automation-institutions-reproducibility-0.1.2-linux-amd64-images.tar.gz
docker load --input .\automation-institutions-reproducibility-0.1.2-linux-amd64-images.tar.gz
docker image inspect book-repro-runtime:0.1.2
docker image inspect book-repro-docs:0.1.2
~~~

Compara las identidades observadas con ENVIRONMENT_MANIFEST.json. Docker puede reutilizar capas ya presentes; la carga verificada acredita la integridad y ejecutabilidad del bundle, pero no una recuperación física desde un almacén vacío.

## Ejecutar la fuente extraída sin red

Desde la raíz del ZIP extraído:

~~~powershell
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 `
  -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work `
  -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" `
  book-repro-runtime:0.1.2 `
  python -m book_repro reproduce --output /work/build/linux-run
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 `
  -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work `
  -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" `
  book-repro-runtime:0.1.2 `
  python -m book_repro verify --run /work/build/linux-run
~~~

/work/build corresponde a build en el anfitrión. Estas órdenes ejecutan la fuente montada. Para diagnosticar el contenido incorporado al construir la imagen, omite el montaje y BOOK_REPRO_ROOT=/work; no confundas esa modalidad con el recorrido receptor.

## Construcción documental desde el bundle

~~~powershell
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 `
  -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work `
  -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" `
  book-repro-docs:0.1.2 `
  python -m book_repro build-docs --run /work/build/linux-run --output /work/build/linux-docs
~~~

## Reconstrucción alternativa

docker build puede requerir red para instalar paquetes Debian. Desde la raíz fuente:

~~~powershell
docker build --platform linux/amd64 --target runtime -t book-repro-runtime:0.1.2 .
docker build --platform linux/amd64 --target docs -t book-repro-docs:0.1.2 .
~~~

No se requiere un nombre universal de contexto: basta un motor Docker que ejecute contenedores Linux. La base y los locks permanecen fijados.

## Windows

El requisito es Windows AMD64, CPython 3.12 y py -3.12. Desde la raíz extraída, limpia variables heredadas y crea un entorno nuevo:

~~~powershell
Remove-Item Env:PYTHONPATH,Env:PYTHONHOME,Env:BOOK_REPRO_ROOT -ErrorAction SilentlyContinue
.\bootstrap_windows.ps1 -VenvPath .venv-0.1.2
~~~

El bootstrap instala sólo desde vendor/wheels y valida locks/requirements-windows.txt.
