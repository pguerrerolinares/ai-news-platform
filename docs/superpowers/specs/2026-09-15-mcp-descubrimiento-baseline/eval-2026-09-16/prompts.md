# Prompts del A/B (10) — superficie vieja vs nueva del MCP ai-news

Perfil de uso: Paul en sesión de brainstorming/mejora de proyectos, buscando qué ha hecho la comunidad o qué dicen los papers sobre un problema concreto; más tendencias de un tema en el tiempo. Cada prompt pide enlaces concretos.

- **q01** (descubrimiento): Estoy diseñando la memoria persistente de un sistema de agentes LLM (notas markdown + búsqueda híbrida). ¿Qué papers o repos recientes proponen cómo consolidar o invalidar la memoria de un agente? Dame los más relevantes con enlace y por qué.
- **q02** (descubrimiento): Quiero dar contexto de código a agentes de programación mediante un grafo del repo. ¿Qué herramientas o papers existen para eso y cuáles tienen tracción real? Enlaces.
- **q03** (descubrimiento): Mis agentes leen contenido de terceros (webscraping, RSS) y me preocupa la prompt injection indirecta. ¿Qué defensas concretas propone la comunidad y qué evidencia hay de que funcionen? Enlaces.
- **q04** (descubrimiento): Estoy montando un pipeline RAG sobre pgvector y quiero medir si el retrieval es bueno. ¿Qué benchmarks, métricas o herramientas de evaluación de retrieval hay ahora mismo? Enlaces.
- **q05** (descubrimiento): Necesito que varios subagentes trabajen sobre el mismo repo sin pisarse. ¿Qué frameworks o papers tratan la orquestación multiagente para tareas de código, y qué problemas reportan? Enlaces.
- **q06** (descubrimiento): Quiero reducir el coste de clasificar 2000+ items/día con LLM. ¿Qué técnicas recientes hay de routing barato, cascadas de modelos o prefiltrado, con resultados medidos? Enlaces.
- **q07** (descubrimiento): Busco modelos open-weights pequeños (menos de ~30B) que sirvan para extraer datos estructurados de texto en local. ¿Cuáles son los candidatos actuales y qué se dice de ellos? Enlaces.
- **q08** (descubrimiento): ¿Qué hay de nuevo en evaluación de agentes de código (benchmarks más allá de SWE-bench, problemas de contaminación, entornos)? Dame lo más citado o comentado con enlaces.
- **q09** (tendencia): ¿Está subiendo el interés por "spec-driven development" para agentes de código en los últimos meses? Justifícalo con datos concretos del corpus, no con impresiones.
- **q10** (tendencia): Compara cómo ha evolucionado la atención a "memoria de agentes" frente a "prompt injection / seguridad de agentes" en los últimos 6 meses. Datos, no impresiones.
