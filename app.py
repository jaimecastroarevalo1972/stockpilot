from io import BytesIO
import pandas as pd
import streamlit as st
from inventory_engine import load_workbook, calculate_recommendations, build_message

st.set_page_config(page_title="StockPilot", page_icon="📦", layout="wide")
st.title("StockPilot")
st.caption("Recomendaciones de compra e inventario para tiendas y micromercados · versión 0.6")
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
start_used = result["fecha_inicio_promedio"].iloc[0].strftime("%d/%m/%y")
end_used = result["fecha_fin_promedio"].iloc[0].strftime("%d/%m/%y")
if days_used < history_days:
    st.warning(f"Se solicitaron {history_days} días, pero el archivo contiene {days_used} días disponibles. El promedio usa únicamente el periodo real: {start_used} a {end_used}.")
else:
    st.info(f"El promedio diario utiliza {days_used} días calendario: {start_used} a {end_used}. Los días sin ventas dentro del periodo cuentan como cero.")
inventory_start = result["fecha_inventario"].min().strftime("%d/%m/%y")
inventory_end = result["fecha_inventario"].max().strftime("%d/%m/%y")
if inventory_start == inventory_end:
    st.success(f"Inventario utilizado: {inventory_end}.")
else:
    st.warning(f"Los productos no tienen el mismo corte de inventario. Fechas utilizadas: {inventory_start} a {inventory_end}. Para cada producto se tomó su registro más reciente.")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Analizados", len(result)); c2.metric("Urgentes", (result["prioridad"]=="URGENTE").sum())
c3.metric("Por comprar", len(buy)); c4.metric("Costo sugerido", f"USD {buy['costo_compra_sugerida'].sum():,.2f}")
summary=buy.groupby("proveedor",as_index=False).agg(productos=("codigo_producto","count"),unidades=("cantidad_sugerida","sum"),costo=("costo_compra_sugerida","sum")).sort_values("costo",ascending=False)

tab_buy, tab_provider, tab_whatsapp, tab_detail = st.tabs(["Qué comprar", "Proveedores", "WhatsApp", "Detalle"])

with tab_buy:
    st.subheader("Recomendaciones prioritarias")
    if buy.empty:
        st.success("No hay compras sugeridas con la configuración actual.")
    else:
        for _, row in buy.iterrows():
            icon = "🔴" if row["prioridad"] == "URGENTE" else "🟠"
            pack = "paquete" if row["paquetes_sugeridos"] == 1 else "paquetes"
            if pd.notna(row["dias_cobertura"]) and row["dias_cobertura"] != float("inf"):
                coverage_days = round(row["dias_cobertura"])
                coverage = f"{coverage_days} día" if coverage_days == 1 else f"{coverage_days} días"
            else:
                coverage = "Sin cálculo"
            next_visit = row["proxima_visita_calculada"].strftime("%d/%m/%y")
            with st.expander(f"{icon} {row['nombre_producto']} · Comprar {row['cantidad_sugerida']:.0f} unidades"):
                st.markdown(
                    f"**Proveedor:** {row['proveedor']}  \n"
                    f"**Presentación:** {row['paquetes_sugeridos']:.0f} {pack}  \n"
                    f"**Stock actual:** {row['cantidad_disponible']:.0f} unidades  \n"
                    f"**Cobertura:** {coverage}  \n"
                    f"**Próxima visita:** {next_visit}  \n"
                    f"**Costo estimado:** USD {row['costo_compra_sugerida']:,.2f}"
                )
        compact = buy[["prioridad","nombre_producto","cantidad_sugerida","paquetes_sugeridos","proveedor","cantidad_disponible","dias_cobertura","proxima_visita_calculada","costo_compra_sugerida"]].copy()
        compact["proxima_visita_calculada"] = compact["proxima_visita_calculada"].dt.strftime("%d/%m/%y")
        compact["dias_cobertura"] = compact["dias_cobertura"].replace(float("inf"), pd.NA).round(1)
        compact = compact.rename(columns={"prioridad":"Prioridad","nombre_producto":"Producto","cantidad_sugerida":"Comprar","paquetes_sugeridos":"Paquetes","proveedor":"Proveedor","cantidad_disponible":"Stock","dias_cobertura":"Cobertura (días)","proxima_visita_calculada":"Próxima visita","costo_compra_sugerida":"Costo USD"})
        with st.expander("Ver tabla compacta"):
            st.dataframe(compact, use_container_width=True, hide_index=True)

with tab_provider:
    st.subheader("Compra por proveedor")
    provider_view = summary.rename(columns={"proveedor":"Proveedor","productos":"Productos","unidades":"Unidades","costo":"Costo USD"})
    st.dataframe(provider_view, use_container_width=True, hide_index=True)

with tab_whatsapp:
    st.subheader("Mensaje para WhatsApp")
    st.caption("Use el botón de copiar del recuadro y pegue el contenido en WhatsApp.")
    st.code(build_message(result, limit=12), language=None)

with tab_detail:
    st.subheader("Detalle del cálculo")
    detail_cols=["prioridad","nombre_producto","proveedor","dias_analizados","fecha_inventario","fecha_ultima_visita","frecuencia_visita_dias","proxima_visita_calculada","cantidad_disponible","venta_promedio_diaria","dias_cobertura","cantidad_sugerida","costo_compra_sugerida","explicacion"]
    detail = result[detail_cols].replace(float("inf"), pd.NA).copy()
    for date_col in ["fecha_inventario", "fecha_ultima_visita", "proxima_visita_calculada"]:
        detail[date_col] = detail[date_col].dt.strftime("%d/%m/%y")
    detail = detail.rename(columns={"prioridad":"Prioridad","nombre_producto":"Producto","proveedor":"Proveedor","dias_analizados":"Días analizados","fecha_inventario":"Fecha inventario","fecha_ultima_visita":"Última visita","frecuencia_visita_dias":"Visita cada (días)","proxima_visita_calculada":"Próxima visita","cantidad_disponible":"Stock","venta_promedio_diaria":"Venta diaria","dias_cobertura":"Cobertura (días)","cantidad_sugerida":"Comprar","costo_compra_sugerida":"Costo USD","explicacion":"Explicación"})
    st.dataframe(detail, use_container_width=True, hide_index=True)

out=BytesIO()
with pd.ExcelWriter(out,engine="openpyxl") as writer:
    result.drop(columns=["orden"]).to_excel(writer,sheet_name="Recomendaciones",index=False)
    summary.to_excel(writer,sheet_name="Resumen proveedores",index=False)
st.download_button("Descargar recomendaciones",out.getvalue(),"Recomendaciones_StockPilot.xlsx")
