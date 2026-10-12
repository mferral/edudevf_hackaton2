# Constitución

1. **Simplicidad**: lo mínimo que funcione; una sola API FastAPI.
2. **Fuente única**: las respuestas salen del RAG (`docs/rag.md`); si no hay dato, el bot lo dice y no inventa.
3. **Seguridad**: toda entrada pasa por Llama Guard (y Prompt Guard si está disponible) antes del LLM.
4. **Memoria por sesión**: historial por número de teléfono, acotado y sin mezclar pacientes.
5. **Citas con reglas**: solo L–J 8–19 h y sáb 8–14 h; pago por adelantado; reagendar con 1 día de anticipación.
6. **Calidad**: Swagger y pruebas unitarias obligatorias; ejecución manual y documentada.
