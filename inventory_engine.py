import math
import pandas as pd

REQUIRED = {
    "Productos": {"codigo_producto", "nombre_producto", "categoria", "proveedor", "unidades_por_paquete", "costo_unitario", "activo"},
    "Ventas": {"fecha", "codigo_producto", "cantidad_vendida"},
    "Inventario": {"fecha_inventario", "codigo_producto", "cantidad_disponible"},
    "Proveedores": {"proveedor", "frecuencia_visita_dias", "fecha_ultima_visita", "dias_entrega", "dias_stock_seguridad"},
}

def load_workbook(source):
    sheets = pd.read_excel(source, sheet_name=None)
    missing = set(REQUIRED) - set(sheets)
    if missing:
        raise ValueError("Faltan las hojas: " + ", ".join(sorted(missing)))
    for name, columns in REQUIRED.items():
        absent = columns - set(sheets[name].columns)
        if absent:
            raise ValueError(f"En {name} faltan: " + ", ".join(sorted(absent)))
    return sheets

def calculate_recommendations(sheets, history_days=56, excess_days=30):
    products = sheets["Productos"].copy()
    products = products[products["activo"].astype(str).str.lower().isin(["sí", "si", "true", "1"])]
    sales = sheets["Ventas"].copy()
    stock = sheets["Inventario"].copy()
    providers = sheets["Proveedores"].copy()
    sales["fecha"] = pd.to_datetime(sales["fecha"], errors="coerce")
    stock["fecha_inventario"] = pd.to_datetime(stock["fecha_inventario"], errors="coerce")
    if sales["fecha"].isna().any():
        raise ValueError("Ventas contiene fechas no válidas.")
    if stock["fecha_inventario"].isna().any():
        raise ValueError("Inventario contiene fechas no válidas.")
    stock["cantidad_disponible"] = pd.to_numeric(stock["cantidad_disponible"], errors="coerce")
    if "cantidad_pendiente_recibir" not in stock:
        stock["cantidad_pendiente_recibir"] = 0
    stock["cantidad_pendiente_recibir"] = pd.to_numeric(stock["cantidad_pendiente_recibir"], errors="coerce").fillna(0)
    if stock["cantidad_disponible"].isna().any():
        raise ValueError("Inventario contiene cantidades disponibles no válidas.")

    duplicate_groups = stock.groupby(["codigo_producto", "fecha_inventario"], dropna=False)
    conflicts = duplicate_groups.agg(
        cantidades_disponibles=("cantidad_disponible", "nunique"),
        cantidades_pendientes=("cantidad_pendiente_recibir", "nunique"),
    ).reset_index()
    conflicts = conflicts[(conflicts["cantidades_disponibles"] > 1) | (conflicts["cantidades_pendientes"] > 1)]
    if not conflicts.empty:
        examples = [f"{row.codigo_producto} ({row.fecha_inventario:%Y-%m-%d})" for row in conflicts.head(5).itertuples()]
        raise ValueError("Hay inventarios contradictorios para el mismo producto y fecha: " + ", ".join(examples) + ". Corrija las cantidades antes de continuar.")
    stock = stock.drop_duplicates(
        ["codigo_producto", "fecha_inventario", "cantidad_disponible", "cantidad_pendiente_recibir"],
        keep="last",
    )
    sales_end_date = sales["fecha"].max().normalize()
    sales_first_date = sales["fecha"].min().normalize()
    analysis_date = max(sales_end_date, stock["fecha_inventario"].max()).normalize()
    providers["fecha_ultima_visita"] = pd.to_datetime(providers["fecha_ultima_visita"], errors="coerce")
    if providers["fecha_ultima_visita"].isna().any():
        raise ValueError("Proveedores contiene fechas de última visita no válidas.")
    for column in ["frecuencia_visita_dias", "dias_entrega", "dias_stock_seguridad"]:
        providers[column] = pd.to_numeric(providers[column], errors="coerce")
    if providers[["frecuencia_visita_dias", "dias_entrega", "dias_stock_seguridad"]].isna().any(axis=None) or (providers["frecuencia_visita_dias"] <= 0).any():
        raise ValueError("Revise la frecuencia, entrega y seguridad de los proveedores.")
    if (providers["fecha_ultima_visita"].dt.normalize() > analysis_date).any():
        invalid = providers.loc[
            providers["fecha_ultima_visita"].dt.normalize() > analysis_date,
            "proveedor",
        ].astype(str).head(5).tolist()
        raise ValueError("La fecha de última visita no puede ser posterior a la fecha de análisis. Revise: " + ", ".join(invalid) + ".")
    def normalize_next_visit(row):
        next_date = row["fecha_ultima_visita"].normalize() + pd.Timedelta(days=row["frecuencia_visita_dias"])
        if next_date < analysis_date:
            elapsed = (analysis_date - next_date).days
            cycles = math.ceil(elapsed / row["frecuencia_visita_dias"])
            next_date += pd.Timedelta(days=cycles * row["frecuencia_visita_dias"])
        return next_date
    providers["proxima_visita_calculada"] = providers.apply(normalize_next_visit, axis=1)
    providers["dias_hasta_proxima_visita"] = (providers["proxima_visita_calculada"] - analysis_date).dt.days
    requested_start = sales_end_date - pd.Timedelta(days=history_days - 1)
    effective_start = max(requested_start, sales_first_date)
    effective_days = (sales_end_date - effective_start).days + 1
    recent = sales[sales["fecha"].between(effective_start, sales_end_date)].copy()
    recent["cantidad_vendida"] = pd.to_numeric(recent["cantidad_vendida"], errors="coerce").fillna(0)
    demand = recent.groupby("codigo_producto", as_index=False)["cantidad_vendida"].sum()
    demand = demand.rename(columns={"cantidad_vendida": "unidades_vendidas_periodo"})
    demand["venta_promedio_diaria"] = demand["unidades_vendidas_periodo"] / effective_days
    stock = stock.sort_values("fecha_inventario").drop_duplicates("codigo_producto", keep="last")
    result = products.merge(demand, on="codigo_producto", how="left")
    result = result.merge(stock[["codigo_producto", "fecha_inventario", "cantidad_disponible", "cantidad_pendiente_recibir"]], on="codigo_producto", how="left")
    result = result.merge(providers, on="proveedor", how="left")
    result["fecha_inicio_promedio"] = effective_start
    result["fecha_fin_promedio"] = sales_end_date
    result["dias_analizados"] = effective_days
    result[["unidades_vendidas_periodo", "venta_promedio_diaria", "cantidad_pendiente_recibir"]] = result[["unidades_vendidas_periodo", "venta_promedio_diaria", "cantidad_pendiente_recibir"]].fillna(0)
    critical = ["cantidad_disponible", "frecuencia_visita_dias", "dias_hasta_proxima_visita", "dias_entrega", "dias_stock_seguridad", "unidades_por_paquete", "costo_unitario"]
    if result[critical].isna().any(axis=None):
        raise ValueError("Faltan datos críticos de inventario o configuración.")
    result["dias_objetivo"] = result["dias_hasta_proxima_visita"] + result["frecuencia_visita_dias"] + result["dias_entrega"] + result["dias_stock_seguridad"]
    result["necesidad_neta"] = (result["venta_promedio_diaria"] * result["dias_objetivo"] - result["cantidad_disponible"] - result["cantidad_pendiente_recibir"]).clip(lower=0)
    result["paquetes_sugeridos"] = result.apply(lambda r: math.ceil(r["necesidad_neta"] / r["unidades_por_paquete"]) if r["necesidad_neta"] > 0 else 0, axis=1)
    result["cantidad_sugerida"] = result["paquetes_sugeridos"] * result["unidades_por_paquete"]
    result["costo_compra_sugerida"] = result["cantidad_sugerida"] * result["costo_unitario"]
    result["dias_cobertura"] = result.apply(lambda r: r["cantidad_disponible"] / r["venta_promedio_diaria"] if r["venta_promedio_diaria"] > 0 else math.inf, axis=1)
    def priority(r):
        if r["venta_promedio_diaria"] == 0 and r["cantidad_disponible"] > 0: return "SIN MOVIMIENTO"
        if r["dias_cobertura"] <= r["dias_hasta_proxima_visita"]: return "URGENTE"
        if r["cantidad_sugerida"] > 0: return "COMPRAR"
        if r["dias_cobertura"] > excess_days: return "EXCESO"
        return "NO COMPRAR"
    result["prioridad"] = result.apply(priority, axis=1)
    order = {"URGENTE": 1, "COMPRAR": 2, "EXCESO": 3, "SIN MOVIMIENTO": 4, "NO COMPRAR": 5}
    result["orden"] = result["prioridad"].map(order)
    def explanation(r):
        if r["prioridad"] == "SIN MOVIMIENTO": return f"No registra ventas en {effective_days} días analizados y mantiene {r['cantidad_disponible']:.0f} unidades."
        if r["prioridad"] == "EXCESO": return f"El inventario cubre aproximadamente {r['dias_cobertura']:.0f} días."
        if r["cantidad_sugerida"] > 0: return f"Tiene {r['cantidad_disponible']:.0f} unidades, vende {r['venta_promedio_diaria']:.1f} por día; {r['proveedor']} visita cada {r['frecuencia_visita_dias']:.0f} días y la próxima visita es en {r['dias_hasta_proxima_visita']:.0f} días."
        return f"El inventario cubre aproximadamente {r['dias_cobertura']:.0f} días."
    result["explicacion"] = result.apply(explanation, axis=1)
    return result.sort_values(["orden", "dias_cobertura", "nombre_producto"]).reset_index(drop=True)

def build_message(result, limit=8):
    buy = result[result["cantidad_sugerida"] > 0]
    lines = ["RECOMENDACIONES DE COMPRA", "", f"Productos por comprar: {len(buy)}", f"Compra sugerida: USD {buy['costo_compra_sugerida'].sum():,.2f}", ""]
    for _, r in buy.head(limit).iterrows():
        pack = "paquete" if r["paquetes_sugeridos"] == 1 else "paquetes"
        lines += [f"{r['prioridad']} - {r['nombre_producto']}", f"Comprar {r['cantidad_sugerida']:.0f} unidades ({r['paquetes_sugeridos']:.0f} {pack}).", r["explicacion"], ""]
    if len(buy) > limit: lines.append(f"Además, hay {len(buy)-limit} productos por revisar.")
    return "\n".join(lines)
