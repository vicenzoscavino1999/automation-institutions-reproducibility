# Uso de la distribución local verificada 0.1.2

El ZIP contiene una única carpeta raíz, definida por config/distribution_inclusion.json. No incluye el manuscrito completo v22, historiales de corridas, entornos virtuales, revisiones internas, prompts, notas de trabajo, CV, correspondencia ni formularios editoriales.

## Orden de verificación

Antes de extraer, usa Get-FileHash para comparar el ZIP y el bundle con SHA256SUMS.txt. Después extrae el ZIP, instala un entorno nuevo y ejecuta verify-package con el intérprete de ese entorno:

~~~powershell
$python = ".\.venv-0.1.2\Scripts\python.exe"
& $python -m book_repro verify-package --archive PATH_TO_DELIVERED_ZIP
~~~

CHECKSUMS.sha256 cubre todos los miembros internos salvo el propio registro. DISTRIBUTION_MANIFEST.json separa las identidades de fuente, documento autónomo y corrida usada para ensamblar. Los checksums detectan cambios respecto de los registros distribuidos; no son firmas independientes de autoría.

## Recorrido principal

RECEIVER_GUIDE_ES.md contiene el flujo literal completo:

1. hashes del sistema;
2. extracción nueva;
3. instalación Windows con CPython 3.12;
4. verify-package con el nuevo intérprete;
5. reproduce y verify;
6. carga del bundle y reproducción Linux sin red;
7. comparación Windows–Linux;
8. construcción e inspección del PDF con la imagen documental.

Los destinos de corrida deben ser nuevos. results/ e independent/ se crean dentro del destino señalado por --output.

## Artefactos externos

El ZIP se acompaña de:

- automation-institutions-reproducibility-0.1.2-linux-amd64-images.tar.gz;
- ENVIRONMENT_MANIFEST.json;
- DEBIAN_PACKAGES.tsv;
- SHA256SUMS.txt;
- automation-institutions-reduced-example-v22-0.1.2.pdf;
- RECEIVER_GUIDE_ES.md.

ENVIRONMENT_MANIFEST.json es la fuente distribuida para los IDs, digests y etiquetas efectivas de las imágenes. DEBIAN_PACKAGES.tsv se obtiene de las imágenes entregadas; no es una lista supuesta.

## Alcance

La distribución reproduce el ejemplo reducido y las comprobaciones finitas declaradas. No resuelve el HANK–New Keynesian completo ni simula los módulos no implementados. coverage funciona estructuralmente sin el libro. coverage --manuscript y check-book requieren la copia v22 identificada por hash y suministrada por separado.

No se afirma ejecución remota de CI, repositorio público, depósito, DOI ni envío editorial. No se concede una licencia nueva.
