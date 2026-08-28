METRICS = {
    "revenue": {
        "description": "Completed payment amount minus completed refunds / 已完成付款减已完成退款",
        "sql": "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) FROM refunds WHERE status='completed'),0),2) AS revenue"
    },
    "completed_orders": {
        "description": "Count of completed orders / 已完成订单数量",
        "sql": "SELECT COUNT(*) AS completed_orders FROM orders WHERE status='completed'"
    },
    "avg_order_value": {
        "description": "Average total for completed orders / 已完成订单平均客单价",
        "sql": "SELECT ROUND(AVG(total),2) AS avg_order_value FROM orders WHERE status='completed'"
    }
}

def resolve_metric(question: str):
    q=question.lower()
    aliases={"收入":"revenue","营收":"revenue","订单数":"completed_orders","客单价":"avg_order_value"}
    for k,v in aliases.items():
        if k in question: return v
    for name in METRICS:
        if name in q: return name
    return None
