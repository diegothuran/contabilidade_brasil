import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, uploadPortalFile, uploadRequestFile } from "../api";

type RequestFile = {
  file_id: string;
  document_id: string;
  file_name: string;
  state: string;
  returned_reason: string | null;
};

type Comment = {
  comment_id: string;
  author_kind: string;
  body: string;
  created_at: string;
};

type Detail = {
  document_request_id: string;
  title: string;
  status: string;
  files: RequestFile[];
  comments: Comment[];
};

export function RequestThread({
  requestId,
  mode,
  onDownload,
}: {
  requestId: string;
  mode: "portal" | "office";
  onDownload: (documentId: string, fileName: string) => void;
}) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const base = mode === "portal" ? `/v1/portal/document-requests/${requestId}` : `/v1/document-requests/${requestId}`;
  const detail = useQuery({
    queryKey: ["request-detail", mode, requestId],
    queryFn: () => api<Detail>(base),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["request-detail", mode, requestId] });
  const comment = useMutation({
    mutationFn: () => api<Comment>(`${base}/comments`, { body: { body: text } }),
    onSuccess: async () => {
      setText("");
      await refresh();
    },
  });
  const send = useMutation({
    mutationFn: () => {
      if (!file) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o arquivo.");
      }
      return mode === "portal" ? uploadPortalFile(requestId, file) : uploadRequestFile(requestId, file);
    },
    onSuccess: async () => {
      setFile(null);
      await refresh();
    },
  });
  const giveBack = useMutation({
    mutationFn: () => api(`${base}/return`, { body: { reason } }),
    onSuccess: async () => {
      setReason("");
      await refresh();
    },
  });
  const failure = comment.error ?? send.error ?? giveBack.error;
  const errorText = failure instanceof ApiError ? failure.message : failure ? "Falha no pedido." : null;
  const item = detail.data;
  const open = item?.status === "open" || item?.status === "received";

  if (detail.isLoading) {
    return <p className="muted">Carregando o pedido.</p>;
  }
  if (detail.isError || !item) {
    return <p className="error">Não foi possível abrir o pedido.</p>;
  }
  return (
    <section className="panel">
      <h2>{item.title}</h2>
      {errorText ? <p className="error">{errorText}</p> : null}
      <ul>
        {item.files.length === 0 ? <li>Nenhum arquivo.</li> : null}
        {item.files.map((entry) => (
          <li key={entry.file_id} style={entry.state === "returned" ? { textDecoration: "line-through" } : undefined}>
            {entry.file_name}
            {entry.state === "returned" ? ` · devolvido. ${entry.returned_reason ?? ""}` : ""}
            <button type="button" className="secondary" onClick={() => onDownload(entry.document_id, entry.file_name)}>
              Baixar
            </button>
          </li>
        ))}
      </ul>
      {open ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            send.mutate();
          }}
        >
          <input type="file" aria-label={`Novo arquivo de ${item.title}`} onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="submit" disabled={!file || send.isPending}>Enviar arquivo</button>
        </form>
      ) : null}
      {mode === "office" && item.status === "received" ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            giveBack.mutate();
          }}
        >
          <input
            value={reason}
            minLength={10}
            placeholder="Motivo da devolução"
            aria-label="Motivo da devolução"
            onChange={(event) => setReason(event.target.value)}
          />
          <button type="submit" className="secondary" disabled={reason.trim().length < 10 || giveBack.isPending}>
            Devolver ao cliente
          </button>
        </form>
      ) : null}
      <h3>Conversa</h3>
      {item.comments.length === 0 ? <p className="muted">Nenhuma mensagem.</p> : null}
      <ul>
        {item.comments.map((entry) => (
          <li key={entry.comment_id}>
            <strong>{entry.author_kind === "client" ? "Cliente" : "Escritório"}</strong> {entry.body}
          </li>
        ))}
      </ul>
      {open ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            comment.mutate();
          }}
        >
          <input
            value={text}
            maxLength={1000}
            placeholder="Mensagem"
            aria-label="Mensagem do pedido"
            onChange={(event) => setText(event.target.value)}
          />
          <button type="submit" disabled={!text.trim() || comment.isPending}>Enviar mensagem</button>
        </form>
      ) : null}
    </section>
  );
}
