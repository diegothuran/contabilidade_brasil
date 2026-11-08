import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../api";
import { formatDate } from "../format";
import { useSession } from "../session";
import { CRC_CATEGORIES, UFS } from "./signatories";

type Registration = {
  cpf: string;
  crc_uf: string;
  crc_number: string;
  crc_category: string;
  crc: string;
  caption: string;
  regularity_number: string | null;
  regularity_valid_until: string | null;
  updated_at: string | null;
};
type MyRegistration = { user_id: string; display_name: string; registration: Registration | null };

export function ProfilePage() {
  const { me } = useSession();
  const current = useQuery({
    queryKey: ["professional-registration", me.tenant_id],
    queryFn: () => api<MyRegistration>("/v1/me/professional-registration"),
  });
  const registration = current.data?.registration ?? null;
  const expired = registration?.regularity_valid_until ? registration.regularity_valid_until < new Date().toISOString().slice(0, 10) : false;

  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">Conta · {me.tenant_name}</span>
          <h1>Perfil</h1>
          <p>
            {me.display_name}. O registro no conselho regional entra na DRE e no Balanço das empresas em que você é o responsável técnico.
            Ele vale só para este escritório; o sistema não consulta o CRC, e o número é o que você declara aqui.
          </p>
        </div>
      </section>
      <section className="panel">
        <h2>Registro profissional</h2>
        {registration ? (
          <p className="muted" data-testid="profile-current">
            Hoje: {registration.caption}
            {registration.regularity_valid_until ? ` · certidão válida até ${formatDate(registration.regularity_valid_until)}` : " · sem certidão de regularidade informada"}
            {expired ? " (vencida)" : ""}.
          </p>
        ) : current.isSuccess ? (
          <p className="muted" data-testid="profile-current">Você ainda não cadastrou o CRC neste escritório.</p>
        ) : null}
        {current.isSuccess ? <RegistrationForm initial={registration} /> : null}
        {current.isError ? <p className="error">Não foi possível ler o registro.</p> : null}
      </section>
    </>
  );
}

// Monta só depois da leitura; os campos começam com o que já está salvo.
function RegistrationForm({ initial }: { initial: Registration | null }) {
  const queryClient = useQueryClient();
  const [cpf, setCpf] = useState(initial?.cpf ?? "");
  const [uf, setUf] = useState(initial?.crc_uf ?? "PE");
  const [number, setNumber] = useState(initial?.crc_number ?? "");
  const [category, setCategory] = useState(initial?.crc_category ?? "contador");
  const [certificate, setCertificate] = useState(initial?.regularity_number ?? "");
  const [validUntil, setValidUntil] = useState(initial?.regularity_valid_until ?? "");
  const [notice, setNotice] = useState("");

  const save = useMutation({
    mutationFn: () =>
      api<MyRegistration>("/v1/me/professional-registration", {
        method: "PUT",
        body: {
          cpf,
          crc_uf: uf,
          crc_number: number,
          crc_category: category,
          regularity_number: certificate.trim() || null,
          regularity_valid_until: validUntil || null,
        },
      }),
    onSuccess: async (saved) => {
      setNotice(`Registro salvo: ${saved.registration?.caption ?? ""}.`);
      await queryClient.invalidateQueries({ queryKey: ["professional-registration"] });
    },
  });

  return (
    <>
      <form
        className="row"
        onSubmit={(event) => {
          event.preventDefault();
          setNotice("");
          save.mutate();
        }}
      >
        <label>
          CPF
          <input data-testid="profile-cpf" value={cpf} inputMode="numeric" autoComplete="off" onChange={(event) => setCpf(event.target.value)} />
        </label>
        <label>
          UF do CRC
          <select data-testid="profile-uf" value={uf} onChange={(event) => setUf(event.target.value)}>
            {UFS.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          Número do registro
          <input data-testid="profile-crc" value={number} placeholder="012345/O-8" onChange={(event) => setNumber(event.target.value)} />
        </label>
        <label>
          Categoria
          <select data-testid="profile-category" value={category} onChange={(event) => setCategory(event.target.value)}>
            {CRC_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Certidão de regularidade (opcional)
          <input data-testid="profile-certificate" value={certificate} placeholder="PE/2026/000123" onChange={(event) => setCertificate(event.target.value)} />
        </label>
        <label>
          Válida até (opcional)
          <input data-testid="profile-valid-until" type="date" value={validUntil} onChange={(event) => setValidUntil(event.target.value)} />
        </label>
        <button type="submit" data-testid="profile-save" disabled={!cpf.trim() || !number.trim() || save.isPending}>
          Salvar registro
        </button>
      </form>
      {notice ? <p className="ok" data-testid="profile-notice">{notice}</p> : null}
      {save.isError ? <p className="error">{save.error instanceof ApiError ? save.error.message : "Falha ao salvar o registro."}</p> : null}
    </>
  );
}
