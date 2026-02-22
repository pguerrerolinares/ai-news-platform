import { HttpHeaders, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { of } from 'rxjs';
import { NewsItem, Briefing } from '../models/news-item';

function paginatedResponse<T>(items: T[]): HttpResponse<T[]> {
  return new HttpResponse({
    status: 200,
    body: items,
    headers: new HttpHeaders({ 'X-Total-Count': items.length.toString() }),
  });
}

// JWT con exp=9999999999 (año ~2286) — pasa el check de AuthService.isAuthenticated()
export const MOCK_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5fQ' +
  '.mockSignature';

const TODAY = new Date().toISOString().slice(0, 10);

const MOCK_ITEMS: NewsItem[] = [
  {
    id: '1',
    title: 'DeepSeek R2 supera a GPT-4o en benchmarks de razonamiento matemático',
    summary:
      'El nuevo modelo de DeepSeek logra resultados sin precedentes en MATH y AIME 2024, alcanzando un 92.3% de precisión y posicionándose como el mejor modelo open-source disponible actualmente.',
    url: 'https://news.ycombinator.com/item?id=1',
    source: 'hackernews',
    topic: 'modelos',
    relevance_score: 0.97,
    dev_value_score: 0.95,
    credibility_score: 0.9,
    priority: 1,
    trending: true,
    published_at: `${TODAY}T08:30:00Z`,
    created_at: `${TODAY}T09:00:00Z`,
    author: 'dwalsh',
    score: 1847,
  },
  {
    id: '2',
    title: 'Anthropic lanza Claude 3.5 Haiku con ventana de contexto de 200K tokens',
    summary:
      'La nueva versión de Haiku ofrece el mejor balance costo-rendimiento del mercado, con soporte nativo para análisis de imágenes y procesamiento de documentos largos a precios reducidos un 40%.',
    url: 'https://anthropic.com/blog/claude-haiku',
    source: 'rss',
    topic: 'modelos',
    relevance_score: 0.95,
    dev_value_score: 0.92,
    credibility_score: 0.98,
    priority: 2,
    trending: true,
    published_at: `${TODAY}T07:15:00Z`,
    created_at: `${TODAY}T07:45:00Z`,
    author: null,
    score: null,
  },
  {
    id: '3',
    title: 'LangGraph 0.3 introduce soporte nativo para agentes multi-modal',
    summary:
      'La nueva versión del framework de LangChain permite construir pipelines complejos que combinan texto, imágenes y audio con gestión de estado persistente entre conversaciones.',
    url: 'https://github.com/langchain-ai/langgraph',
    source: 'github',
    topic: 'herramientas',
    relevance_score: 0.93,
    dev_value_score: 0.97,
    credibility_score: 0.92,
    priority: 3,
    trending: false,
    published_at: `${TODAY}T06:00:00Z`,
    created_at: `${TODAY}T06:30:00Z`,
    author: null,
    score: 312,
  },
  {
    id: '4',
    title: 'Flash Attention 3 reduce uso de memoria un 45% para secuencias largas',
    summary:
      'El nuevo algoritmo de atención eficiente optimiza operaciones matriciales en H100 y A100, permitiendo procesar contextos de 1M tokens con el mismo hardware que antes requería 512K.',
    url: 'https://arxiv.org/abs/2307.08691',
    source: 'arxiv',
    topic: 'papers',
    relevance_score: 0.93,
    dev_value_score: 0.96,
    credibility_score: 0.94,
    priority: 4,
    trending: false,
    published_at: '2026-02-18T16:00:00Z',
    created_at: '2026-02-18T16:30:00Z',
    author: 'Dao et al.',
    score: null,
  },
  {
    id: '5',
    title: 'Ollama 0.7 añade cuantización GGUF de 2 bits para Llama 3.1 70B en 16GB',
    summary:
      'La popular herramienta para ejecutar modelos localmente incorpora cuantización de 2 bits que permite correr Llama 3.1 70B en GPUs de 16GB con mínima pérdida de calidad.',
    url: 'https://github.com/ollama/ollama',
    source: 'github',
    topic: 'herramientas',
    relevance_score: 0.91,
    dev_value_score: 0.96,
    credibility_score: 0.89,
    priority: 5,
    trending: true,
    published_at: `${TODAY}T05:00:00Z`,
    created_at: `${TODAY}T05:30:00Z`,
    author: null,
    score: 289,
  },
  {
    id: '6',
    title: 'OpenAI anuncia integración de Sora con la API de asistentes para vídeos de 60s',
    summary:
      'Los desarrolladores podrán generar vídeos de hasta 60 segundos desde la API, con controles granulares sobre estilo, movimiento de cámara y coherencia temporal entre clips.',
    url: 'https://openai.com/blog/sora-api',
    source: 'rss',
    topic: 'productos',
    relevance_score: 0.94,
    dev_value_score: 0.9,
    credibility_score: 0.97,
    priority: 6,
    trending: true,
    published_at: `${TODAY}T10:00:00Z`,
    created_at: `${TODAY}T10:15:00Z`,
    author: null,
    score: null,
  },
  {
    id: '7',
    title: 'Mixtral 8x22B lanzado como open-source con licencia Apache 2.0',
    summary:
      'Mistral AI publica su modelo mixture-of-experts más potente bajo licencia permisiva. Supera a GPT-3.5 en la mayoría de benchmarks y puede ejecutarse en hardware de consumo.',
    url: 'https://news.ycombinator.com/item?id=7',
    source: 'hackernews',
    topic: 'open_source',
    relevance_score: 0.96,
    dev_value_score: 0.98,
    credibility_score: 0.93,
    priority: 7,
    trending: true,
    published_at: `${TODAY}T11:30:00Z`,
    created_at: `${TODAY}T12:00:00Z`,
    author: 'mistral_ai',
    score: 2341,
  },
  {
    id: '8',
    title: 'AutoGen 2.0: Microsoft rediseña el framework de agentes conversacionales',
    summary:
      'La nueva versión introduce arquitectura basada en eventos que permite coordinar decenas de agentes especializados con comunicación asíncrona y capacidades de recuperación ante fallos.',
    url: 'https://github.com/microsoft/autogen',
    source: 'github',
    topic: 'agentes',
    relevance_score: 0.92,
    dev_value_score: 0.95,
    credibility_score: 0.91,
    priority: 8,
    trending: false,
    published_at: '2026-02-18T18:00:00Z',
    created_at: '2026-02-18T18:30:00Z',
    author: null,
    score: 198,
  },
  {
    id: '9',
    title: 'UE publica borrador de regulaciones para sistemas de IA de alto riesgo',
    summary:
      'La Comisión Europea presenta el reglamento técnico con criterios de auditoría, transparencia y responsabilidad para sistemas de IA usados en decisiones críticas: crédito, empleo y seguridad.',
    url: 'https://ec.europa.eu/ai-act',
    source: 'rss',
    topic: 'regulacion',
    relevance_score: 0.87,
    dev_value_score: 0.75,
    credibility_score: 0.96,
    priority: 9,
    trending: false,
    published_at: '2026-02-18T14:00:00Z',
    created_at: '2026-02-18T14:30:00Z',
    author: null,
    score: null,
  },
  {
    id: '10',
    title: 'Hugging Face lanza Inference Endpoints con cuantización dinámica',
    summary:
      'La plataforma de modelos open source añade opción de cuantización en tiempo real para reducir costos de inferencia hasta 60%, manteniendo la calidad del modelo original.',
    url: 'https://huggingface.co/blog/inference-endpoints',
    source: 'huggingface',
    topic: 'herramientas',
    relevance_score: 0.9,
    dev_value_score: 0.93,
    credibility_score: 0.95,
    priority: 10,
    trending: false,
    published_at: `${TODAY}T03:00:00Z`,
    created_at: `${TODAY}T03:30:00Z`,
    author: null,
    score: null,
  },
  {
    id: '11',
    title: 'Gemini 2.0 Ultra disponible en Google AI Studio con acceso gratuito para investigadores',
    summary:
      'Google abre acceso al modelo más avanzado de la familia Gemini para investigadores académicos, con cuotas generosas y soporte para multimodalidad nativa incluyendo audio y video.',
    url: 'https://reddit.com/r/MachineLearning/gemini-ultra',
    source: 'reddit',
    topic: 'modelos',
    relevance_score: 0.94,
    dev_value_score: 0.91,
    credibility_score: 0.88,
    priority: 11,
    trending: true,
    published_at: `${TODAY}T13:00:00Z`,
    created_at: `${TODAY}T13:30:00Z`,
    author: 'u/ai_researcher',
    score: 1243,
  },
  {
    id: '12',
    title: 'DSPy: programación declarativa de prompts alcanza 10K estrellas en GitHub',
    summary:
      'El framework de Stanford para optimización automática de prompts y pipelines LLM alcanza un hito importante, con casos de uso en producción reportados por empresas Fortune 500.',
    url: 'https://github.com/stanfordnlp/dspy',
    source: 'github',
    topic: 'herramientas',
    relevance_score: 0.89,
    dev_value_score: 0.94,
    credibility_score: 0.9,
    priority: 12,
    trending: false,
    published_at: '2026-02-18T12:00:00Z',
    created_at: '2026-02-18T12:30:00Z',
    author: null,
    score: 167,
  },
  {
    id: '13',
    title: 'Investigadores desarrollan técnica para detectar alucinaciones en LLMs en tiempo real',
    summary:
      'Nuevo método basado en análisis de incertidumbre epistémica identifica respuestas alucinadas con 87% de precisión sin necesidad de ground truth, reduciendo errores en aplicaciones críticas.',
    url: 'https://arxiv.org/abs/2402.12345',
    source: 'arxiv',
    topic: 'papers',
    relevance_score: 0.91,
    dev_value_score: 0.93,
    credibility_score: 0.95,
    priority: 13,
    trending: false,
    published_at: '2026-02-18T10:00:00Z',
    created_at: '2026-02-18T10:30:00Z',
    author: 'Zhang et al.',
    score: null,
  },
  {
    id: '14',
    title: 'CrewAI lanza marketplace de agentes especializados para casos de uso empresarial',
    summary:
      'La plataforma de orquestación multi-agente abre su ecosistema con más de 150 agentes pre-entrenados para tareas como análisis financiero, revisión legal e investigación de mercado.',
    url: 'https://news.ycombinator.com/item?id=14',
    source: 'hackernews',
    topic: 'agentes',
    relevance_score: 0.88,
    dev_value_score: 0.87,
    credibility_score: 0.85,
    priority: 14,
    trending: false,
    published_at: '2026-02-18T08:00:00Z',
    created_at: '2026-02-18T08:30:00Z',
    author: 'crewai_founder',
    score: 543,
  },
  {
    id: '15',
    title: 'Phi-4 de Microsoft: estado del arte en razonamiento matemático con solo 14B parámetros',
    summary:
      'El modelo supera a modelos 10 veces más grandes en benchmarks matemáticos gracias a un proceso de entrenamiento sintético basado en generación de datos de alta calidad.',
    url: 'https://huggingface.co/microsoft/phi-4',
    source: 'huggingface',
    topic: 'modelos',
    relevance_score: 0.93,
    dev_value_score: 0.95,
    credibility_score: 0.94,
    priority: 15,
    trending: false,
    published_at: '2026-02-17T12:00:00Z',
    created_at: '2026-02-17T12:30:00Z',
    author: null,
    score: null,
  },
  {
    id: '16',
    title: 'vLLM 0.4 introduce PagedAttention v2 con throughput 3x superior',
    summary:
      'La librería de inferencia de alto rendimiento actualiza su algoritmo de gestión de KV-cache, logrando una reducción del 70% en latencia de primer token y soporte para modelos de 400B.',
    url: 'https://github.com/vllm-project/vllm',
    source: 'github',
    topic: 'open_source',
    relevance_score: 0.92,
    dev_value_score: 0.97,
    credibility_score: 0.91,
    priority: 16,
    trending: false,
    published_at: '2026-02-17T06:00:00Z',
    created_at: '2026-02-17T06:30:00Z',
    author: null,
    score: 234,
  },
  {
    id: '17',
    title: 'Llama 3.2 multimodal: análisis de imágenes comparables a GPT-4V en open source',
    summary:
      'Meta publica el conjunto completo de modelos Llama 3.2, incluyendo versiones vision de 11B y 90B con capacidades comparables a GPT-4V, bajo licencia open source permisiva.',
    url: 'https://reddit.com/r/LocalLLaMA/llama32',
    source: 'reddit',
    topic: 'open_source',
    relevance_score: 0.95,
    dev_value_score: 0.96,
    credibility_score: 0.93,
    priority: 17,
    trending: true,
    published_at: '2026-02-16T18:00:00Z',
    created_at: '2026-02-16T18:30:00Z',
    author: 'u/metaai',
    score: 2891,
  },
  {
    id: '18',
    title: 'Perplexity lanza API de búsqueda semántica con citaciones verificadas',
    summary:
      'El motor de búsqueda IA ofrece acceso programático a búsquedas en tiempo real con fuentes verificadas, dirigido a desarrolladores que necesitan información actualizada en sus aplicaciones.',
    url: 'https://news.ycombinator.com/item?id=18',
    source: 'hackernews',
    topic: 'productos',
    relevance_score: 0.89,
    dev_value_score: 0.91,
    credibility_score: 0.87,
    priority: 18,
    trending: false,
    published_at: '2026-02-17T09:00:00Z',
    created_at: '2026-02-17T09:30:00Z',
    author: 'perplexity_team',
    score: 876,
  },
  {
    id: '19',
    title: 'China impone nuevas restricciones de licencias para modelos de IA generativa',
    summary:
      'El gobierno chino exige registro obligatorio y auditorías de seguridad para todos los modelos de IA generativa con más de 1M usuarios, con sanciones de hasta 500M CNY por incumplimiento.',
    url: 'https://www.reuters.com/china-ai-regulation',
    source: 'rss',
    topic: 'regulacion',
    relevance_score: 0.85,
    dev_value_score: 0.7,
    credibility_score: 0.92,
    priority: 19,
    trending: false,
    published_at: '2026-02-17T15:00:00Z',
    created_at: '2026-02-17T15:30:00Z',
    author: null,
    score: null,
  },
  {
    id: '20',
    title: 'Mamba 2: arquitectura de estado selectivo supera transformers en velocidad de inferencia',
    summary:
      'El paper presenta mejoras al modelo de espacio de estado que logra 5x más throughput que un transformer equivalente en secuencias largas, con calidad comparable en benchmarks de lenguaje.',
    url: 'https://arxiv.org/abs/2405.21060',
    source: 'arxiv',
    topic: 'papers',
    relevance_score: 0.9,
    dev_value_score: 0.92,
    credibility_score: 0.93,
    priority: 20,
    trending: false,
    published_at: '2026-02-16T14:00:00Z',
    created_at: '2026-02-16T14:30:00Z',
    author: 'Dao, Gu et al.',
    score: null,
  },
];

const MOCK_TOPICS = {
  topics: ['modelos', 'herramientas', 'papers', 'productos', 'open_source', 'agentes', 'regulacion'],
};

function makeBriefing(date: string, withItems: boolean): Briefing {
  const seed = date.charCodeAt(8) + date.charCodeAt(9);
  const total = 75 + (seed % 45);
  const afterDedup = Math.floor(total * 0.78);
  const filtered = Math.floor(afterDedup * 0.38);
  const trending = Math.floor(filtered * 0.22);
  return {
    date,
    total_items: total,
    items_extracted: total,
    items_after_dedup: afterDedup,
    items_filtered: filtered,
    trending_count: trending,
    duration_seconds: 42 + (seed % 28),
    sources_used: { sources: ['hackernews', 'arxiv', 'reddit', 'rss', 'github', 'huggingface'] },
    generated_at: `${date}T09:00:00Z`,
    items: withItems ? MOCK_ITEMS : [],
  };
}

// Generate 14 days of briefings ending today
const MOCK_BRIEFINGS: Briefing[] = Array.from({ length: 14 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (13 - i));
  const dateStr = d.toISOString().slice(0, 10);
  return makeBriefing(dateStr, dateStr === TODAY);
});

export const mockApiInterceptor: HttpInterceptorFn = (req, next) => {
  const url = req.url;

  // POST /api/auth/token
  if (req.method === 'POST' && url === '/api/auth/token') {
    return of(new HttpResponse({ status: 200, body: { access_token: MOCK_JWT, token_type: 'bearer' } }));
  }

  // GET /api/briefings (all) — must check before /api/briefings/:date
  if (req.method === 'GET' && url === '/api/briefings') {
    return of(paginatedResponse(MOCK_BRIEFINGS));
  }

  // GET /api/briefings/:date
  if (req.method === 'GET' && url.startsWith('/api/briefings/')) {
    const date = url.slice('/api/briefings/'.length);
    const found = MOCK_BRIEFINGS.find((b) => b.date === date);
    if (found) {
      return of(new HttpResponse({ status: 200, body: found }));
    }
    return of(new HttpResponse({ status: 200, body: makeBriefing(date, false) }));
  }

  // GET /api/items/today — must check before /api/items
  if (req.method === 'GET' && url === '/api/items/today') {
    return of(paginatedResponse(MOCK_ITEMS));
  }

  // GET /api/items (archive / generic)
  if (req.method === 'GET' && url === '/api/items') {
    return of(paginatedResponse(MOCK_ITEMS));
  }

  // GET /api/topics
  if (req.method === 'GET' && url === '/api/topics') {
    return of(new HttpResponse({ status: 200, body: MOCK_TOPICS }));
  }

  // GET /api/search
  if (req.method === 'GET' && url === '/api/search') {
    const q = req.params.get('q')?.toLowerCase() ?? '';
    const topic = req.params.get('topic');
    let results = MOCK_ITEMS.filter(
      (item) => item.title.toLowerCase().includes(q) || (item.summary ?? '').toLowerCase().includes(q),
    );
    if (topic) results = results.filter((item) => item.topic === topic);
    const sliced = results.slice(0, 20);
    return of(paginatedResponse(sliced));
  }

  return next(req);
};
