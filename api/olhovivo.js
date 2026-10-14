/**
 * Proxy para a API Olho Vivo (SPTrans) v2.1.
 *
 * O token NUNCA vai para o navegador: ele fica na variável de ambiente
 * SPTRANS_TOKEN do projeto na Vercel. Esta função autentica na SPTrans
 * (POST /Login/Autenticar), guarda o cookie de sessão enquanto a instância
 * estiver viva e repassa só as consultas da lista abaixo.
 *
 * Uso: /api/olhovivo?op=linhas&termosBusca=8000
 */
const BASE = "https://api.olhovivo.sptrans.com.br/v2.1";

// op -> [caminho, parâmetros aceitos, segundos de cache na CDN]
const OPS = {
  status: [null, [], 0],
  linhas: ["/Linha/Buscar", ["termosBusca"], 3600],
  linhaSentido: ["/Linha/BuscarLinhaSentido", ["termosBusca", "sentido"], 3600],
  paradas: ["/Parada/Buscar", ["termosBusca"], 3600],
  paradasLinha: ["/Parada/BuscarParadasPorLinha", ["codigoLinha"], 3600],
  paradasCorredor: ["/Parada/BuscarParadasPorCorredor", ["codigoCorredor"], 3600],
  corredores: ["/Corredor", [], 3600],
  empresas: ["/Empresa", [], 3600],
  posicao: ["/Posicao", [], 15],
  posicaoLinha: ["/Posicao/Linha", ["codigoLinha"], 15],
  posicaoGaragem: ["/Posicao/Garagem", ["codigoEmpresa", "codigoLinha"], 15],
  previsao: ["/Previsao", ["codigoParada", "codigoLinha"], 15],
  previsaoLinha: ["/Previsao/Linha", ["codigoLinha"], 15],
  previsaoParada: ["/Previsao/Parada", ["codigoParada"], 15],
};

let cookie = null; // reaproveitado entre chamadas enquanto a instância estiver quente

async function autenticar(token) {
  const resp = await fetch(`${BASE}/Login/Autenticar?token=${encodeURIComponent(token)}`, {
    method: "POST",
    signal: AbortSignal.timeout(15000),
  });
  const texto = (await resp.text()).trim().toLowerCase();
  if (resp.status !== 200) {
    const e = new Error(
      `A SPTrans recusou a autenticação (HTTP ${resp.status}). Ela às vezes bloqueia IPs de provedores de nuvem.`
    );
    e.codigo = "auth";
    throw e;
  }
  if (texto !== "true") {
    const e = new Error("A SPTrans recusou o token (respondeu 'false'). Gere um novo token em 'Meus Aplicativos'.");
    e.codigo = "auth";
    throw e;
  }
  const sets = typeof resp.headers.getSetCookie === "function" ? resp.headers.getSetCookie() : [resp.headers.get("set-cookie") || ""];
  cookie = sets.map((c) => c.split(";")[0]).filter(Boolean).join("; ");
}

async function chamar(path, params) {
  const url = `${BASE}${path}${params.toString() ? `?${params}` : ""}`;
  return fetch(url, { headers: { Cookie: cookie || "", Accept: "application/json" }, signal: AbortSignal.timeout(20000) });
}

module.exports = async (req, res) => {
  const q = req.query || {};
  const op = String(q.op || "");
  const def = OPS[op];
  if (!def) return res.status(400).json({ erro: "operação inválida" });

  const token = process.env.SPTRANS_TOKEN;
  if (!token) {
    return res.status(503).json({
      erro: "token_ausente",
      mensagem: "Configure a variável de ambiente SPTRANS_TOKEN no projeto da Vercel e faça um novo deploy.",
    });
  }

  const [path, aceitos, ttl] = def;
  const params = new URLSearchParams();
  for (const k of aceitos) {
    const v = q[k];
    if (v == null || v === "") continue;
    const s = String(v);
    if (k === "termosBusca" ? s.length > 80 : !/^\d{1,10}$/.test(s)) {
      return res.status(400).json({ erro: `parâmetro inválido: ${k}` });
    }
    params.set(k, s);
  }
  // /Linha/Buscar exige a chave na URL, mesmo vazia
  if (aceitos.includes("termosBusca") && !params.has("termosBusca")) params.set("termosBusca", "");

  try {
    if (!cookie) await autenticar(token);
    if (op === "status") {
      res.setHeader("Cache-Control", "no-store");
      return res.status(200).json({ ok: true });
    }

    let resp = await chamar(path, params);
    if (resp.status === 401) {
      cookie = null;
      await autenticar(token);
      resp = await chamar(path, params);
    }
    const texto = await resp.text();
    if (resp.status !== 200) {
      return res.status(502).json({ erro: `Erro HTTP ${resp.status} da SPTrans em ${path}`, detalhe: texto.slice(0, 300) });
    }
    res.setHeader("Cache-Control", ttl ? `public, s-maxage=${ttl}, stale-while-revalidate=${ttl}` : "no-store");
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    return res.status(200).send(texto || "null");
  } catch (e) {
    cookie = null;
    const status = e.codigo === "auth" ? 401 : 502;
    const msg = e.name === "TimeoutError" || e.name === "AbortError" ? "A SPTrans não respondeu a tempo." : e.message;
    return res.status(status).json({ erro: e.codigo === "auth" ? "auth" : "conexao", mensagem: msg });
  }
};
