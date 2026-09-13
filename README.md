[README.md](https://github.com/user-attachments/files/32157267/README.md)
# StockPilot 0.5

1. Descomprima el archivo.
2. Ejecute `Iniciar_StockPilot.bat` en Windows.
3. En la aplicación cargue `Plantilla_StockPilot_Demo.xlsx`.

La primera ejecución requiere Python e Internet para instalar los componentes. La hoja `Proveedores` registra la fecha de la última visita, cada cuántos días visita el proveedor, los días de entrega y los días de seguridad. El sistema calcula la siguiente visita y, si ya pasó, avanza ciclos completos hasta obtener la siguiente fecha vigente. El demo calcula venta diaria promedio, cobertura, cantidad sugerida ajustada a paquetes y costo estimado. Las reglas deben calibrarse con datos reales antes de utilizarlas para efectuar compras.

## Ajuste de la versión 0.3

El promedio utiliza como máximo los días seleccionados, pero nunca divide entre más días de los que realmente contiene el archivo. La fecha final del promedio corresponde a la última fecha de ventas, independientemente de la fecha del inventario. La aplicación muestra el periodo y los días utilizados.

## Ajuste de la versión 0.4

La hoja Inventario puede contener varios cortes históricos por producto. Se utiliza el registro de fecha más reciente. Los duplicados idénticos del mismo producto y fecha se consolidan; si tienen cantidades diferentes, la aplicación detiene el proceso y solicita corregirlos. La pantalla muestra la fecha de inventario utilizada y advierte cuando los productos tienen cortes distintos.

## Ajuste de la versión 0.5

La próxima visita se calcula desde `fecha_ultima_visita + frecuencia_visita_dias`. Si esa fecha ya pasó respecto a la fecha de análisis, se avanza por ciclos de la misma frecuencia. La aplicación detiene el procesamiento si falta la última visita, si la fecha no es válida o si aparece después de la fecha de análisis.
