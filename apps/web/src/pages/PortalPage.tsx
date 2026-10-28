import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, downloadPortalDocument, uploadPortalFile, uploadPortalSubmission } from "../api";
import { userManager } from "../auth";
import { formatCnpj } from "../format";
import { RequestThread } from "./RequestThread";
import { Me } from "../session";

type PortalRequest = {
  document_request_id: string;
  title: string;
  due_on: string;
  period: string;
  status: string;
  document_id: string | null;
  file_name: string | null;
  blocks_close: boolean;
  cancel_reason: string | null;
  received_at: string | null;
  confirmed_at: string | null;
};

type PortalList = {
  items: PortalRequest[];
  next_cursor: string | null;
  summary: { open: number; received: number; overdue: number; next_due_on: string | null };
};

const STATUS: Record<string, string> = {
  open: "Pedido aberto",
  received: "Arquivo recebido",
  confirmed: "Pedido confirmado",
  cancelled: "Pedido cancelado",
};

function day(value: string | null): string {
  if (!value) return "";
  return value.slice(0, 10).split("-").reverse().join("/");
}

export function PortalPage({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"open" | "history">("open");
  const [openId, setOpenId] = useState<string | null>(null);
  const [fileById, setFileById] = useState<Record<string, File | null>>({});
  const [looseFile, setLooseFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const loose = useMutation({
    mutationFn: () => {
      if (!looseFile) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o arquivo.");
      }
      return uploadPortalSubmission(looseFile, note);
    },
    onSuccess: async () => {
      setLooseFile(null);
      setNote("");
    },
  });
  const preference = useQuery({
    queryKey: ["portal-preference", me.user_id],
    queryFn: () => api<{ notify_client: boolean }>("/v1/portal/preferences"),
  });
  const savePreference = useMutation({
    mutationFn: (notify: boolean) => api("/v1/portal/preferences", { method: "PATCH", body: { notify_client: notify } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal-preference", me.user_id] }),
  });
  const requests = useQuery({
    queryKey: ["portal-requests", me.legal_entity_id, tab],
    queryFn: () =>
      api<PortalList>(
        tab === "history" ? "/v1/portal/document-requests?status=confirmed,cancelled" : "/v1/portal/document-requests",
      ),
  });
  const send = useMutation({
    mutationFn: (requestId: string) => {
      const file = fileById[requestId];
      if (!file) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o arquivo deste pedido.");
      }
      return uploadPortalFile(requestId, file);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portal-requests", me.legal_entity_id] });
    },
  });
  const errorText =
    send.error instanceof ApiError
      ? send.error.message
      : loose.error instanceof ApiError
        ? loose.error.message
        : send.error || loose.error
          ? "Falha ao enviar o arquivo."
          : null;
  const summary = requests.data?.summary;

  return (
    <main className="rastro">
      <section className="page-container">
        <section className="page-header">
          <div>
            <span className="eyebrow">{me.tenant_name}</span>
            <h1>{me.legal_entity_name ?? "Sua empresa"}</h1>
            <p>{me.legal_entity_cnpj ? `CNPJ ${formatCnpj(me.legal_entity_cnpj)}` : "Pedidos desta empresa."}</p>
          </div>
          <div className="page-header__action">
            <label>
              <input
                type="checkbox"
                checked={preference.data?.notify_client ?? true}
                onChange={(event) => savePreference.mutate(event.target.checked)}
              />
              Receber avisos por e-mail
            </label>
            <button type="button" onClick={() => void userManager.signoutRedirect()}>Sair</button>
          </div>
        </section>
        {summary ? (
          <section className="metric-strip" aria-label="Resumo dos pedidos">
            <article className="metric metric--attention"><span>Abertos</span><strong>{summary.open}</strong><small>sem arquivo</small></article>
            <article className="metric metric--info"><span>Recebidos</span><strong>{summary.received}</strong><small>aguardam o escritório</small></article>
            <article className="metric metric--danger"><span>Vencidos</span><strong>{summary.overdue}</strong><small>prazo já passou</small></article>
            <article className="metric metric--neutral"><span>Próximo prazo</span><strong>{summary.next_due_on ? day(summary.next_due_on) : "—"}</strong><small>entre os pedidos em aberto</small></article>
          </section>
        ) : null}
        <section className="panel">
          <h2>Enviar documento sem pedido</h2>
          <p className="muted">O escritório classifica o arquivo. Este envio não bloqueia o fechamento.</p>
          <form
            className="row"
            onSubmit={(event) => {
              event.preventDefault();
              loose.mutate();
            }}
          >
            <input type="file" aria-label="Documento sem pedido" onChange={(event) => setLooseFile(event.target.files?.[0] ?? null)} />
            <input value={note} maxLength={500} placeholder="Nota, se quiser" aria-label="Nota do documento" onChange={(event) => setNote(event.target.value)} />
            <button type="submit" disabled={!looseFile || loose.isPending}>Enviar documento</button>
          </form>
        </section>
        <section className="panel">
          <div className="row">
            <button type="button" className={tab === "open" ? "" : "secondary"} onClick={() => setTab("open")}>Em aberto</button>
            <button type="button" className={tab === "history" ? "" : "secondary"} onClick={() => setTab("history")}>Histórico</button>
          </div>
          <h2>{tab === "open" ? "Pedidos" : "Histórico"}</h2>
          <p className="muted">Envie o arquivo pedido. Confirmar fica com o escritório. Esta tela não mostra lançamentos.</p>
          {requests.isLoading ? <p className="muted">Carregando pedidos.</p> : null}
          {requests.isError ? <p className="error">Não foi possível carregar os pedidos.</p> : null}
          {errorText ? <p className="error">{errorText}</p> : null}
          {requests.data && requests.data.items.length === 0 ? (
            <p className="muted">{tab === "open" ? "Nenhum pedido aberto." : "Nenhum pedido confirmado ou cancelado."}</p>
          ) : null}
          {requests.data && requests.data.items.length > 0 ? (
            <table>
              <thead>
                <tr><th>Pedido</th><th>Mês de referência</th><th>Prazo</th><th>Estado</th><th></th></tr>
              </thead>
              <tbody>
                {requests.data.items.map((item) => (
                  <tr key={item.document_request_id}>
                    <td>{item.title}</td>
                    <td>{item.period}</td>
                    <td>{day(item.due_on)}</td>
                    <td>
                      {STATUS[item.status] ?? item.status}
                      {item.blocks_close ? " · bloqueia o fechamento" : ""}
                      {item.cancel_reason ? <p className="muted">Motivo: {item.cancel_reason}</p> : null}
                      {item.received_at ? <p className="muted">Arquivo em {day(item.received_at)}</p> : null}
                      {item.confirmed_at ? <p className="muted">Confirmado em {day(item.confirmed_at)}</p> : null}
                    </td>
                    <td>
                      {item.status === "open" ? (
                        <form
                          className="row"
                          onSubmit={(event) => {
                            event.preventDefault();
                            send.mutate(item.document_request_id);
                          }}
                        >
                          <input
                            type="file"
                            aria-label={`Arquivo de ${item.title}`}
                            onChange={(event) =>
                              setFileById((current) => ({ ...current, [item.document_request_id]: event.target.files?.[0] ?? null }))
                            }
                          />
                          <button type="submit" disabled={!fileById[item.document_request_id] || send.isPending}>Enviar arquivo</button>
                        </form>
                      ) : null}
                      {item.document_id ? (
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => void downloadPortalDocument(item.document_id ?? "", item.file_name || `${item.title}.arquivo`)}
                        >
                          Baixar arquivo
                        </button>
                      ) : null}
                      <button type="button" className="secondary" onClick={() => setOpenId(item.document_request_id)}>
                        Abrir pedido
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {openId ? (
            <RequestThread
              requestId={openId}
              mode="portal"
              onDownload={(documentId, fileName) => void downloadPortalDocument(documentId, fileName)}
            />
          ) : null}
        </section>
      </section>
    </main>
  );
}
