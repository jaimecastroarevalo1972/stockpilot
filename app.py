from io import BytesIO
import pandas as pd
import streamlit as st
from inventory_engine import load_workbook, calculate_recommendations, build_message

st.set_page_config(page_title="StockPilot", page_icon="📦", layout="wide")
st.title("StockPilot")
st.caption("Recomendaciones de compra e inventario para tiendas y micromercados · versión 0.5")
with st.sidebar:
    st.header("Configuración")
    history_days = st.slider("Días de ventas para analizar", 14, 90, 56, 7)
    excess_days = st.slider("Cobertura considerada excesiva", 15, 90, 30, 5)
file = st.file_uploader("Cargue la plantilla de productos, ventas e inventario", type=["xlsx"])
if file is None:
    st.info("Utilice Plantilla_StockPilot_Demo.xlsx incluida en esta carpeta.")
    st.write("El demo recomendará qué comprar, cuánto comprar y qué productos tienen exceso de inventario.")
    st.stop()
try:
    result = calculate_recommendations(load_workbook(file), history_days, excess_days)
except Exception as exc:
    st.error(f"No se pudo procesar el archivo: {exc}")
    st.stop()
buy = result[result["cantidad_sugerida"] > 0]
days_used = int(result["dias_analizados"].iloc[0])
start_used = result["fecha_inicio_promedio"].iloc[0].strftime("%Y-%m-%d")
end_used = result["fecha_fin_promedio"].iloc[0].strftime("%Y-%m-%d")
if days_used < history_days:
    st.warning(f"Se solicitaron {history_days} días, pero el archivo contiene {days_used} días disponibles. El promedio usa únicamente el periodo real: {start_used} a {end_used}.")
else:
    st.info(f"El promedio diario utiliza {days_used} días calendario: {start_used} a {end_used}. Los días sin ventas dentro del periodo cuentan como cero.")
inventory_start = result["fecha_inventario"].min().strftime("%Y-%m-%d")
inventory_end = result["fecha_inventario"].max().strftime("%Y-%m-%d")
if inventory_start == inventory_end:
    st.success(f"Inventario utilizado: {inventory_end}.")
else:
    st.warning(f"Los productos no tienen el mismo corte de inventario. Fechas utilizadas: {inventory_start} a {inventory_end}. Para cada producto se tomó su registro más reciente.")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Productos analizados", len(result)); c2.metric("Compra urgente", (result["prioridad"]=="URGENTE").sum())
c3.metric("Productos por comprar", len(buy)); c4.metric("Costo sugerido", f"USD {buy['costo_compra_sugerida'].sum():,.2f}")
st.subheader("Recomendaciones prioritarias")
cols=["prioridad","nombre_producto","proveedor","dias_analizados","fecha_inventario","fecha_ultima_visita","frecuencia_visita_dias","proxima_visita_calculada","cantidad_disponible","venta_promedio_diaria","dias_cobertura","cantidad_sugerida","costo_compra_sugerida","explicacion"]
st.dataframe(result[cols].replace(float("inf"), pd.NA), use_container_width=True, hide_index=True)
left,right=st.columns([1.1,.9])
summary=buy.groupby("proveedor",as_index=False).agg(productos=("codigo_producto","count"),unidades=("cantidad_sugerida","sum"),costo=("costo_compra_sugerida","sum")).sort_values("costo",ascending=False)
with left: st.subheader("Compra por proveedor"); st.dataframe(summary,use_container_width=True,hide_index=True)
with right: st.subheader("Vista previa de WhatsApp"); st.code(build_message(result),language=None)
out=BytesIO()
with pd.ExcelWriter(out,engine="openpyxl") as writer:
    result.drop(columns=["orden"]).to_excel(writer,sheet_name="Recomendaciones",index=False)
    summary.to_excel(writer,sheet_name="Resumen proveedores",index=False)
st.download_button("Descargar recomendaciones",out.getvalue(),"Recomendaciones_StockPilot.xlsx")
