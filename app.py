from io import BytesIO
import pandas as pd
import streamlit as st
from inventory_engine import load_workbook, calculate_recommendations, build_message


def money(value):
    return f"{value:,.2f}"


def provider_summary(data):
    if data.empty:
        return pd.DataFrame(columns=["Proveedor", "Productos", "Unidades", "Costo USD"])
    return (
        data.groupby("proveedor", as_index=False)
        .agg(Productos=("codigo_producto", "count"), Unidades=("cantidad_sugerida", "sum"), Costo_USD=("costo_compra_sugerida", "sum"))
        .rename(columns={"proveedor": "Proveedor", "Costo_USD": "Costo USD"})
        .sort_values("Costo USD", ascending=False)
    )


def recommendation_cards(data, icon):
    if data.empty:
        st.info("No hay productos en esta prioridad.")
        return
    for _, row in data.iterrows():
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
                f"**Venta promedio:** {row['venta_promedio_diaria']:.2f} unidades por día  \n"
                f"**Cobertura:** {coverage}  \n"
                f"**Próxima visita:** {next_visit}  \n"
                f"**Costo estimado:** USD {money(row['costo_compra_sugerida'])}"
            )


st.set_page_config(page_title="StockPilot", page_icon="📦", layout="wide")
st.title("StockPilot")
st.caption("Recomendaciones de compra e inventario para tiendas y micromercados · versión 0.8")
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
    sheets = load_workbook(file)
    result = calculate_recommendations(sheets, history_days, excess_days)
except Exception as exc:
    st.error(f"No se pudo procesar el archivo: {exc}")
    st.stop()

urgent = result[result["prioridad"] == "URGENTE"].copy()
high = result[result["prioridad"] == "COMPRAR"].copy()
buy = pd.concat([urgent, high], ignore_index=True)
excess = result[result["prioridad"] == "EXCESO"].copy()
excess["valor_inventario"] = excess["cantidad_disponible"] * excess["costo_unitario"]
urgent_summary = provider_summary(urgent)
high_summary = provider_summary(high)
summary = provider_summary(buy)

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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Analizados", len(result))
c2.metric("Urgentes", len(urgent))
c3.metric("Prioridad alta", len(high))
c4.metric("Con exceso", len(excess))

tab_buy, tab_provider, tab_inventory, tab_products, tab_whatsapp, tab_detail = st.tabs(["Qué comprar", "Proveedores", "Inventario", "Productos", "WhatsApp", "Detalle"])

with tab_buy:
    st.subheader(f"Recomendaciones prioritarias (USD {money(urgent['costo_compra_sugerida'].sum())})")
    recommendation_cards(urgent, "🔴")
    st.subheader(f"Recomendaciones prioridad alta (USD {money(high['costo_compra_sugerida'].sum())})")
    recommendation_cards(high, "🟡")

    if not buy.empty:
        compact = buy[["prioridad", "nombre_producto", "venta_promedio_diaria", "cantidad_disponible", "dias_cobertura", "cantidad_sugerida", "paquetes_sugeridos", "proveedor", "proxima_visita_calculada", "costo_compra_sugerida"]].copy()
        compact["prioridad"] = compact["prioridad"].replace({"URGENTE": "Urgente", "COMPRAR": "Prioridad alta"})
        compact["proxima_visita_calculada"] = compact["proxima_visita_calculada"].dt.strftime("%d/%m/%y")
        compact["dias_cobertura"] = compact["dias_cobertura"].replace(float("inf"), pd.NA).round(1)
        compact["venta_promedio_diaria"] = compact["venta_promedio_diaria"].round(2)
        compact = compact.rename(columns={"prioridad": "Prioridad", "nombre_producto": "Producto", "venta_promedio_diaria": "Venta diaria", "cantidad_disponible": "Stock", "dias_cobertura": "Cobertura (días)", "cantidad_sugerida": "Comprar", "paquetes_sugeridos": "Paquetes", "proveedor": "Proveedor", "proxima_visita_calculada": "Próxima visita", "costo_compra_sugerida": "Costo USD"})
        with st.expander("Ver tabla compacta"):
            st.dataframe(compact, use_container_width=True, hide_index=True)

    st.subheader(f"Exceso de inventario (USD {money(excess['valor_inventario'].sum())})")
    if excess.empty:
        st.success("No hay productos con cobertura superior al límite configurado.")
    else:
        with st.expander(f"Ver productos con exceso ({len(excess)})"):
            st.caption(f"Productos con más de {excess_days} días de cobertura.")
            excess_view = excess[["nombre_producto", "proveedor", "venta_promedio_diaria", "cantidad_disponible", "dias_cobertura", "valor_inventario"]].copy()
            excess_view["venta_promedio_diaria"] = excess_view["venta_promedio_diaria"].round(2)
            excess_view["dias_cobertura"] = excess_view["dias_cobertura"].round(1)
            excess_view = excess_view.rename(columns={"nombre_producto": "Producto", "proveedor": "Proveedor", "venta_promedio_diaria": "Venta diaria", "cantidad_disponible": "Stock", "dias_cobertura": "Cobertura (días)", "valor_inventario": "Valor inventario USD"})
            st.dataframe(excess_view, use_container_width=True, hide_index=True)

    st.subheader(f"Resumen de compras por proveedor (USD {money(buy['costo_compra_sugerida'].sum())})")
    st.markdown(f"**Críticos — Total: USD {money(urgent['costo_compra_sugerida'].sum())}**")
    st.dataframe(urgent_summary, use_container_width=True, hide_index=True) if not urgent_summary.empty else st.info("No hay compras críticas.")
    st.markdown(f"**Prioridad alta — Total: USD {money(high['costo_compra_sugerida'].sum())}**")
    st.dataframe(high_summary, use_container_width=True, hide_index=True) if not high_summary.empty else st.info("No hay compras de prioridad alta.")

with tab_provider:
    st.subheader("Información de proveedores")
    provider_data = sheets["Proveedores"].copy()
    provider_data["fecha_ultima_visita"] = pd.to_datetime(provider_data["fecha_ultima_visita"], errors="coerce").dt.strftime("%d/%m/%y")
    computed_visits = result[["proveedor", "proxima_visita_calculada"]].drop_duplicates("proveedor")
    provider_data = provider_data.merge(computed_visits, on="proveedor", how="left")
    provider_data["proxima_visita_calculada"] = provider_data["proxima_visita_calculada"].dt.strftime("%d/%m/%y")
    provider_data = provider_data[["proveedor", "fecha_ultima_visita", "frecuencia_visita_dias", "proxima_visita_calculada", "dias_entrega", "dias_stock_seguridad"]]
    provider_data = provider_data.rename(columns={"proveedor": "Proveedor", "fecha_ultima_visita": "Última visita", "frecuencia_visita_dias": "Visita cada (días)", "proxima_visita_calculada": "Próxima visita", "dias_entrega": "Días de entrega", "dias_stock_seguridad": "Stock de seguridad (días)"})
    st.dataframe(provider_data, use_container_width=True, hide_index=True)

with tab_inventory:
    st.subheader("Inventario más reciente por producto")
    inventory_data = sheets["Inventario"].copy()
    inventory_data["fecha_inventario"] = pd.to_datetime(inventory_data["fecha_inventario"], errors="coerce")
    inventory_data = inventory_data.sort_values("fecha_inventario").drop_duplicates("codigo_producto", keep="last")
    product_names = sheets["Productos"][["codigo_producto", "nombre_producto"]].drop_duplicates("codigo_producto")
    inventory_data = inventory_data.merge(product_names, on="codigo_producto", how="left")
    if "cantidad_pendiente_recibir" not in inventory_data:
        inventory_data["cantidad_pendiente_recibir"] = 0
    inventory_data["fecha_inventario"] = inventory_data["fecha_inventario"].dt.strftime("%d/%m/%y")
    inventory_data = inventory_data[["codigo_producto", "nombre_producto", "fecha_inventario", "cantidad_disponible", "cantidad_pendiente_recibir"]]
    inventory_data = inventory_data.rename(columns={"codigo_producto": "Código", "nombre_producto": "Producto", "fecha_inventario": "Fecha inventario", "cantidad_disponible": "Stock", "cantidad_pendiente_recibir": "Pendiente de recibir"})
    st.dataframe(inventory_data, use_container_width=True, hide_index=True)

with tab_products:
    st.subheader("Catálogo de productos")
    st.caption("Vista de consulta para revisar los datos principales registrados en la plantilla.")
    product_data = sheets["Productos"].copy()
    product_columns = ["codigo_producto", "nombre_producto", "categoria", "proveedor", "unidades_por_paquete", "costo_unitario"]
    if "precio_venta" in product_data.columns:
        product_columns.append("precio_venta")
    product_columns.append("activo")
    product_data = product_data[product_columns].rename(columns={"codigo_producto": "Código", "nombre_producto": "Producto", "categoria": "Categoría", "proveedor": "Proveedor", "unidades_por_paquete": "Unidades por paquete", "costo_unitario": "Costo unitario USD", "precio_venta": "Precio de venta USD", "activo": "Activo"})
    st.dataframe(product_data, use_container_width=True, hide_index=True)

with tab_whatsapp:
    st.subheader("Mensaje para WhatsApp")
    st.caption("Use el botón de copiar del recuadro y pegue el contenido en WhatsApp.")
    st.code(build_message(result, limit=12), language=None)

with tab_detail:
    st.subheader("Detalle del cálculo")
    detail_cols = ["prioridad", "nombre_producto", "proveedor", "dias_analizados", "fecha_inventario", "fecha_ultima_visita", "frecuencia_visita_dias", "proxima_visita_calculada", "cantidad_disponible", "venta_promedio_diaria", "dias_cobertura", "cantidad_sugerida", "costo_compra_sugerida", "explicacion"]
    detail = result[detail_cols].replace(float("inf"), pd.NA).copy()
    for date_col in ["fecha_inventario", "fecha_ultima_visita", "proxima_visita_calculada"]:
        detail[date_col] = detail[date_col].dt.strftime("%d/%m/%y")
    detail = detail.rename(columns={"prioridad": "Prioridad", "nombre_producto": "Producto", "proveedor": "Proveedor", "dias_analizados": "Días analizados", "fecha_inventario": "Fecha inventario", "fecha_ultima_visita": "Última visita", "frecuencia_visita_dias": "Visita cada (días)", "proxima_visita_calculada": "Próxima visita", "cantidad_disponible": "Stock", "venta_promedio_diaria": "Venta diaria", "dias_cobertura": "Cobertura (días)", "cantidad_sugerida": "Comprar", "costo_compra_sugerida": "Costo USD", "explicacion": "Explicación"})
    st.dataframe(detail, use_container_width=True, hide_index=True)

out = BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    result.drop(columns=["orden"]).to_excel(writer, sheet_name="Recomendaciones", index=False)
    summary.to_excel(writer, sheet_name="Resumen proveedores", index=False)
st.download_button("Descargar recomendaciones", out.getvalue(), "Recomendaciones_StockPilot.xlsx")
