import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, uploadRequestFile } from "../api";
import { can, useSession } from "../session";

type RequestItem = {
  document_request_id: string;
  document_type: string;
  title: string;
  due_on: string;
  status: string;
  document_id: string | null;
  cancel_reason: string | null;
};

const TYPES = [
  ["receipt", "Recibo"],
  ["invoice", "Nota"],
  ["contract", "Contrato"],
  ["bank_statement", "Extrato"],
  ["journal_support", "Suporte de lançamento"],
  ["tax_file", "Arquivo fiscal"],
  ["government_response", "Retorno de órgão"],
  ["other", "Outro"],
] as const;

const REQUEST_STATUS: Record<string, string> = {
  open: "Pedido aberto",
  received: "Arquivo recebido",
  confirmed: "Confirmado",
  cancelled: "Cancelado",
};

function typeLabel(value: string): string {
  return TYPES.find(([key]) => key === value)?.[1] ?? value;
}

export function DocumentRequestsPage() {
  const { entityId, periodId, me } = useSession();
  const queryClient = useQueryClient();
  const [documentType, setDocumentType] = useState("receipt");
  const [title, setTitle] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [fileById, setFileById] = useState<Record<string, File | null>>({});
  const [reasonById, setReasonById] = useState<Record<string, string>>({});
  const requests = useQuery({
    queryKey: ["document-requests", entityId, periodId],
    enabled: Boolean(entityId && periodId),
    queryFn: () =>
      api<{ items: RequestItem[] }>(`/v1/document-requests?legal_entity_id=${entityId}&period_id=${periodId}`),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["document-requests", entityId, periodId] });
  const create = useMutation({
    mutationFn: () =>
      api<RequestItem>("/v1/document-requests", {
        body: { legal_entity_id: entityId, period_id: periodId, document_type: documentType, title, due_on: dueOn },
      }),
    onSuccess: async () => {
      setTitle("");
      setDueOn("");
      await refresh();
    },
  });
  const sendFile = useMutation({
    mutationFn: (requestId: string) => {
      const file = fileById[requestId];
      if (!file) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o arquivo deste pedido.");
      }
      return uploadRequestFile(requestId, file);
    },
    onSuccess: async (_result, requestId) => {
      setFileById((current) => ({ ...current, [requestId]: null }));
      await refresh();
    },
  });
  const confirm = useMutation({
    mutationFn: (requestId: string) => api<RequestItem>(`/v1/document-requests/${requestId}/confirm`, { body: {} }),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: (requestId: string) =>
      api<RequestItem>(`/v1/document-requests/${requestId}/cancel`, { body: { reason: reasonById[requestId] ?? "" } }),
    onSuccess: refresh,
  });
  const failure = create.error ?? sendFile.error ?? confirm.error ?? cancel.error;
  const errorText = failure instanceof ApiError ? `${failure.title}. ${failure.message}` : failure ? "Falha no pedido." : null;
  const canAsk = can(me.roles, "preparer", "admin");
  const canSend = can(me.roles, "preparer", "approver", "admin");
  const canConfirm = can(me.roles, "approver", "admin");
  const canCancel = can(me.roles, "preparer", "approver", "admin");

  return (
    <section>
      <h1>Pendências</h1>
      <p className="muted">O pedido fica nesta empresa e nesta competência. O arquivo original entra no mesmo armazenamento das evidências, com hash. Confirmar não publica lançamento.</p>
      {!periodId ? <p className="muted">Escolha a competência na barra.</p> : null}
      {canAsk && periodId ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Título
            <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={200} />
          </label>
          <label>
            Tipo
            <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              {TYPES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Prazo
            <input type="date" value={dueOn} onChange={(event) => setDueOn(event.target.value)} required />
          </label>
          <button type="submit" disabled={create.isPending || !title.trim()}>Pedir documento</button>
        </form>
      ) : null}
      {errorText ? <p className="error">{errorText}</p> : null}
      {requests.isLoading ? <p className="muted">Carregando pedidos.</p> : null}
      {requests.isError ? <p className="error">Não foi possível listar os pedidos desta competência.</p> : null}
      {requests.data && requests.data.items.length === 0 ? <p className="muted">Nenhum pedido nesta competência.</p> : null}
      {requests.data && requests.data.items.length > 0 ? (
        <table>
          <thead>
            <tr><th>Pedido</th><th>Tipo</th><th>Prazo</th><th>Estado</th><th></th></tr>
          </thead>
          <tbody>
            {requests.data.items.map((item) => (
              <tr key={item.document_request_id}>
                <td>{item.title}</td>
                <td>{typeLabel(item.document_type)}</td>
                <td>{item.due_on.split("-").reverse().join("/")}</td>
                <td>{REQUEST_STATUS[item.status] ?? item.status}</td>
                <td>
                  {item.status === "open" && canSend ? (
                    <form
                      className="row"
                      onSubmit={(event) => {
                        event.preventDefault();
                        sendFile.mutate(item.document_request_id);
                      }}
                    >
                      <input
                        type="file"
                        aria-label={`Arquivo de ${item.title}`}
                        onChange={(event) =>
                          setFileById((current) => ({ ...current, [item.document_request_id]: event.target.files?.[0] ?? null }))
                        }
                      />
                      <button type="submit" disabled={!fileById[item.document_request_id] || sendFile.isPending}>Enviar arquivo</button>
                    </form>
                  ) : null}
                  {item.status === "received" && canConfirm ? (
                    <button type="button" onClick={() => confirm.mutate(item.document_request_id)} disabled={confirm.isPending}>
                      Confirmar
                    </button>
                  ) : null}
                  {(item.status === "open" || item.status === "received") && canCancel ? (
                    <form
                      className="row"
                      onSubmit={(event) => {
                        event.preventDefault();
                        cancel.mutate(item.document_request_id);
                      }}
                    >
                      <input
                        value={reasonById[item.document_request_id] ?? ""}
                        placeholder="Motivo do cancelamento"
                        aria-label={`Motivo para cancelar ${item.title}`}
                        onChange={(event) =>
                          setReasonById((current) => ({ ...current, [item.document_request_id]: event.target.value }))
                        }
                      />
                      <button type="submit" className="secondary" disabled={cancel.isPending}>
                        Cancelar pedido
                      </button>
                    </form>
                  ) : null}
                  {item.cancel_reason ? <p className="muted">{item.cancel_reason}</p> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
