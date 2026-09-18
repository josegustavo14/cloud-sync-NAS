import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Cloud,
  LayoutDashboard,
  FolderOpen,
  RefreshCw,
  History,
  Settings,
  Plus,
  ArrowDown,
  HardDrive,
  ShieldCheck,
  Search,
  X,
  Play,
  Pause,
  LogOut,
  AlertCircle,
  ChevronRight,
  Copy,
  Check,
  LoaderCircle,
} from "lucide-react";
import { bytes, date, progress, request } from "./api";
import "./style.css";

const providers = {
  google_drive: "Google Drive",
  onedrive: "OneDrive",
  dropbox: "Dropbox",
  filesystem: "Dispositivo / pasta",
  takeout: "Google Takeout",
};
const statuses = {
  started: "Na fila",
  running: "Sincronizando",
  completed: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
};
const tabs = [
  ["dashboard", "Visão geral", LayoutDashboard],
  ["accounts", "Contas", Cloud],
  ["sync", "Sincronização", RefreshCw],
  ["files", "Arquivos", FolderOpen],
  ["history", "Histórico", History],
  ["settings", "Configurações", Settings],
];

function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem("pcs-token") || "",
  );
  const [tab, setTab] = useState("dashboard");
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState(false);
  const [logJob, setLogJob] = useState(null);
  const api = useCallback(
    (path, options) => request(path, token, options),
    [token],
  );
  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [d, a, j] = await Promise.all([
        api("/dashboard"),
        api("/accounts"),
        api("/jobs"),
      ]);
      setDashboard(d);
      setAccounts(a);
      setJobs(j);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, [api, token]);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);
  async function action(path, body, method = "POST") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, {
        method,
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      await refresh();
      setNotice("Solicitação concluída.");
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  function login(value) {
    sessionStorage.setItem("pcs-token", value);
    setToken(value);
  }
  function logout() {
    sessionStorage.removeItem("pcs-token");
    setToken("");
    setDashboard(null);
    setError("");
  }
  if (!token) return <Login onLogin={login} />;
  const active = dashboard?.active_jobs || [];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={() => setTab("dashboard")}>
          <span className="brand-icon">
            <Cloud size={25} />
          </span>
          <span>
            Personal
            <br />
            <strong>Cloud Sync</strong>
          </span>
        </a>
        <div className="workspace">
          <span className="status-dot" /> Meu servidor{" "}
          <span className="local-label">Local</span>
        </div>
        <nav aria-label="Navegação principal">
          {tabs.map(([id, title, Icon]) => (
            <button
              key={id}
              className={tab === id ? "nav-item selected" : "nav-item"}
              onClick={() => setTab(id)}
            >
              <Icon size={19} />
              {title}
              {id === "sync" && active.length > 0 && (
                <span className="count">{active.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={22} />
          <p>
            Seus arquivos, em casa.<small>As origens são preservadas.</small>
          </p>
        </div>
        <button className="nav-item logout" onClick={logout}>
          <LogOut size={17} /> Sair
        </button>
      </aside>
      <main>
        <header className="topbar">
          <span>
            Meu espaço <ChevronRight size={14} />{" "}
            {tabs.find((t) => t[0] === tab)[1]}
          </span>
          <span className="server-status">
            <span className={`status-dot ${error ? "offline" : ""}`} />
            {error
              ? "Verifique a conexão"
              : dashboard
                ? "Servidor conectado"
                : "Conectando…"}
          </span>
        </header>
        <div className="page">
          {error && (
            <div role="alert" className="message error">
              <AlertCircle size={18} />
              {error}
              <button aria-label="Fechar mensagem" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="message success">
              <Check size={18} />
              {notice}
              <button
                aria-label="Fechar mensagem"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <div className="page-heading">
            <div>
              <h1>{tabs.find((t) => t[0] === tab)[1]}</h1>
              <p>
                {
                  {
                    dashboard: "Todas as suas nuvens. Um lugar para guardar.",
                    accounts: "Conecte as origens da sua biblioteca.",
                    sync: "Acompanhe o que está chegando ao seu servidor.",
                    files: "Uma biblioteca, com todas as suas origens.",
                    history: "Cada sincronização fica registrada.",
                    settings: "Seu servidor, do seu jeito.",
                  }[tab]
                }
              </p>
            </div>
            <button
              className="primary"
              disabled={busy || !accounts.some((a) => a.enabled)}
              onClick={() => action("/sync")}
            >
              <RefreshCw size={17} className={busy ? "spin" : ""} /> Sincronizar
              tudo
            </button>
          </div>
          {tab === "dashboard" && (
            <>
              <section className="flow-panel">
                <div className="flow-copy">
                  <span className="flow-emblem">
                    <ShieldCheck size={24} />
                  </span>
                  <h2>
                    Sua biblioteca está
                    <br />
                    no lugar certo.
                  </h2>
                  <p>
                    Uma cópia local dos seus arquivos.
                    <br />
                    Sem alterar nada nas suas contas.
                  </p>
                </div>
                <div className="flow">
                  <div className="source-clouds">
                    <Cloud />
                    <span>{dashboard?.accounts || 0} origens conectadas</span>
                  </div>
                  <div className="flow-line">
                    <ArrowDown size={18} />
                    <span>Somente leitura</span>
                  </div>
                  <div className="destination">
                    <HardDrive size={25} />
                    <div>
                      <strong>Biblioteca local</strong>
                      <span>/DATA/CloudSync/data</span>
                    </div>
                    <ShieldCheck size={20} />
                  </div>
                </div>
              </section>
              <section className="stats">
                <Stat
                  label="Arquivos únicos"
                  value={(dashboard?.files || 0).toLocaleString("pt-BR")}
                  note={`${dashboard?.origins || 0} origens de arquivos`}
                />
                <Stat
                  label="Biblioteca local"
                  value={bytes(dashboard?.stored_bytes)}
                  note="Conteúdo preservado por SHA-256"
                />
                <Stat
                  label="Espaço disponível"
                  value={bytes(dashboard?.storage.free)}
                  note={
                    dashboard
                      ? `de ${bytes(dashboard.storage.total)} no disco`
                      : "Consultando o servidor"
                  }
                />
                <Stat
                  label="Última sincronização"
                  value={date(dashboard?.last_sync)}
                  note={`Próxima: ${date(dashboard?.next_sync)}`}
                  small
                />
              </section>
              <div className="section-heading">
                <h2>
                  Suas contas <span className="muted">{accounts.length}</span>
                </h2>
                <button className="text-button" onClick={() => setModal(true)}>
                  <Plus size={16} /> Adicionar conta
                </button>
              </div>
              <AccountList
                accounts={accounts}
                busy={busy}
                action={action}
                onAdd={() => setModal(true)}
                compact
              />
              <div className="section-heading">
                <h2>Atividade recente</h2>
                <button
                  className="text-button"
                  onClick={() => setTab("history")}
                >
                  Ver histórico <ChevronRight size={16} />
                </button>
              </div>
              {jobs.length ? (
                <JobList
                  jobs={jobs.slice(0, 3)}
                  action={action}
                  onLogs={setLogJob}
                />
              ) : (
                <Empty
                  icon={History}
                  title="Tudo começa com a primeira cópia"
                  text="Adicione uma conta e inicie a sincronização. Você poderá acompanhar cada etapa aqui."
                />
              )}
              {!!dashboard?.recent_errors.length && (
                <div className="message error">
                  <AlertCircle size={18} />
                  {dashboard.recent_errors.length} erro(s) recente(s). Consulte
                  os logs no histórico.
                </div>
              )}
            </>
          )}
          {tab === "accounts" && (
            <>
              <div className="section-heading">
                <h2>Origens conectadas</h2>
                <button className="primary" onClick={() => setModal(true)}>
                  <Plus size={17} /> Adicionar conta
                </button>
              </div>
              <AccountList
                accounts={accounts}
                action={action}
                busy={busy}
                onAdd={() => setModal(true)}
              />
              <OAuthHelp api={api} />
            </>
          )}
          {tab === "sync" &&
            (active.length ? (
              <JobList jobs={active} action={action} onLogs={setLogJob} />
            ) : (
              <Empty
                icon={RefreshCw}
                title="Nenhuma sincronização em andamento"
                text="Inicie uma conta ou sincronize todas. O servidor continua trabalhando mesmo quando você fecha esta página."
              />
            ))}
          {tab === "history" && (
            <HistoryView
              jobs={jobs}
              api={api}
              action={action}
              onLogs={setLogJob}
              accounts={accounts}
            />
          )}
          {tab === "files" && <Files api={api} accounts={accounts} />}
          {tab === "settings" && <SettingsView api={api} logout={logout} />}
          <footer>
            <Cloud size={15} /> Personal Cloud Sync{" "}
            <span>Armazenamento local. Controle seu.</span>
          </footer>
        </div>
      </main>
      {modal && (
        <AccountModal
          api={api}
          onClose={() => setModal(false)}
          onSave={async (body) => {
            if (await action("/accounts", body)) setModal(false);
          }}
        />
      )}
      {logJob && (
        <Logs api={api} job={logJob} onClose={() => setLogJob(null)} />
      )}
    </div>
  );
}

function Login({ onLogin }) {
  const [value, setValue] = useState("");
  return (
    <div className="login">
      <div className="login-intro">
        <Cloud size={42} />
        <h1>
          Suas nuvens.
          <br />
          Sua casa.
        </h1>
        <p>Guarde uma cópia dos seus arquivos no seu próprio servidor.</p>
      </div>
      <form
        className="login-form"
        onSubmit={(e) => {
          e.preventDefault();
          onLogin(value);
        }}
      >
        <h2>Conectar ao servidor</h2>
        <p>Use o token configurado na instalação.</p>
        <label>
          Token de acesso
          <input
            type="password"
            required
            minLength={32}
            autoComplete="current-password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <button className="primary">
          Entrar <ChevronRight size={17} />
        </button>
        <small>O token permanece apenas nesta sessão do navegador.</small>
      </form>
    </div>
  );
}
function Stat({ label, value, note, small }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong className={small ? "small-value" : ""}>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
function Empty({ icon: Icon, title, text, children }) {
  return (
    <div className="empty">
      <Icon size={30} />
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}
function AccountList({ accounts, busy, action, onAdd, compact }) {
  if (!accounts.length)
    return (
      <Empty
        icon={Cloud}
        title="Traga seus arquivos para casa"
        text="Conecte Google Drive, OneDrive, Dropbox, um dispositivo ou uma exportação do Google Takeout."
      >
        <button className="primary" onClick={onAdd}>
          <Plus size={16} /> Adicionar primeira conta
        </button>
      </Empty>
    );
  return (
    <div className="account-list">
      {accounts.map((a) => (
        <article className="account-row" key={a.id}>
          <span className={`provider-icon ${a.provider}`}>
            <Cloud size={22} />
          </span>
          <div className="account-name">
            <strong>{a.name}</strong>
            <span>{providers[a.provider]}</span>
          </div>
          <span className={`badge ${a.enabled ? "completed" : "cancelled"}`}>
            {a.enabled ? "Ativa" : "Desativada"}
          </span>
          <label className="schedule">
            Frequência
            <select
              aria-label={`Frequência de ${a.name}`}
              disabled={busy}
              value={a.interval_minutes}
              onChange={(e) =>
                action(
                  `/accounts/${a.id}`,
                  { interval_minutes: Number(e.target.value) },
                  "PATCH",
                )
              }
            >
              {![0, 60, 360, 1440, 10080].includes(a.interval_minutes) && (
                <option value={a.interval_minutes}>
                  {a.interval_minutes} min
                </option>
              )}
              <option value="0">Manual</option>
              <option value="60">A cada hora</option>
              <option value="360">A cada 6 horas</option>
              <option value="1440">Diariamente</option>
              <option value="10080">Semanalmente</option>
            </select>
          </label>
          <button
            className="secondary"
            disabled={busy || !a.enabled}
            onClick={() => action(`/accounts/${a.id}/sync`)}
          >
            <RefreshCw size={15} /> Sincronizar
          </button>
          {!compact && (
            <button
              className="icon-button"
              aria-label={
                a.enabled ? `Desativar ${a.name}` : `Ativar ${a.name}`
              }
              disabled={busy}
              onClick={() =>
                action(`/accounts/${a.id}`, { enabled: !a.enabled }, "PATCH")
              }
            >
              {a.enabled ? <Pause size={17} /> : <Play size={17} />}
            </button>
          )}
        </article>
      ))}
    </div>
  );
}
function JobList({ jobs, action, onLogs }) {
  return (
    <div className="job-list">
      {jobs.map((j) => (
        <article className="job" key={j.id}>
          <div className="job-title">
            <div>
              <strong>{j.account_name}</strong>
              <small>{date(j.started_at)}</small>
            </div>
            <span className={`badge ${j.status}`}>{statuses[j.status]}</span>
            <button className="text-button" onClick={() => onLogs(j)}>
              Logs
            </button>
            {["started", "running"].includes(j.status) && (
              <button
                className="icon-button"
                aria-label="Cancelar sincronização"
                onClick={() => action(`/jobs/${j.id}/cancel`)}
              >
                <X size={16} />
              </button>
            )}
          </div>
          <div className="job-counters">
            {[
              ["Encontrados", j.found],
              ["Existentes", j.existing],
              ["Novos", j.new],
              ["Duplicados", j.duplicates],
              ["Baixados", j.downloaded],
              ["Erros", j.errors],
            ].map(([label, value]) => (
              <span key={label}>
                <strong>{value}</strong>
                {label}
              </span>
            ))}
          </div>
          <div className="progress-row">
            <progress
              max="100"
              value={progress(j)}
              aria-label="Progresso da sincronização"
            />
            <span>{progress(j)}%</span>
          </div>
          {j.current_file && <p className="current-file">{j.current_file}</p>}
        </article>
      ))}
    </div>
  );
}
function HistoryView({ jobs, api, action, onLogs, accounts }) {
  const [account, setAccount] = useState("");
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    api(`/jobs?offset=${page * 100}${account ? `&account_id=${account}` : ""}`)
      .then((r) => {
        if (alive) {
          setRows(r);
          setError("");
        }
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [api, account, page, jobs]);
  return (
    <>
      <label className="filter-label">
        Conta
        <select
          value={account}
          onChange={(e) => {
            setAccount(e.target.value);
            setPage(0);
          }}
        >
          <option value="">Todas as contas</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {rows.length ? (
        <JobList jobs={rows} action={action} onLogs={onLogs} />
      ) : (
        <Empty
          icon={History}
          title="Nenhuma sincronização registrada"
          text="O histórico aparecerá aqui após a primeira execução."
        />
      )}
      <Pagination page={page} setPage={setPage} hasNext={rows.length === 100} />
    </>
  );
}
function Pagination({ page, setPage, hasNext }) {
  return (
    <div className="pagination">
      <button
        className="secondary"
        disabled={!page}
        onClick={() => setPage(page - 1)}
      >
        Anterior
      </button>
      <span>Página {page + 1}</span>
      <button
        className="secondary"
        disabled={!hasNext}
        onClick={() => setPage(page + 1)}
      >
        Próxima
      </button>
    </div>
  );
}
function Files({ api, accounts }) {
  const [q, setQ] = useState("");
  const [provider, setProvider] = useState("");
  const [account, setAccount] = useState("");
  const [ext, setExt] = useState("");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [origins, setOrigins] = useState([]);
  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      const query = new URLSearchParams({
        q,
        provider,
        extension: ext,
        offset: String(page * 100),
      });
      if (account) query.set("account_id", account);
      api(`/files?${query}`)
        .then((r) => {
          if (alive) {
            setResult(r);
            setError("");
          }
        })
        .catch((e) => alive && setError(e.message));
    }, 200);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [api, q, provider, account, ext, page]);
  const filter = (setter) => (e) => {
    setter(e.target.value);
    setPage(0);
  };
  return (
    <>
      <div className="filters">
        <label className="search">
          <Search size={19} />
          <input
            aria-label="Buscar arquivos"
            placeholder="Buscar nome, caminho ou SHA-256…"
            value={q}
            onChange={filter(setQ)}
          />
        </label>
        <select
          aria-label="Filtrar provider"
          value={provider}
          onChange={filter(setProvider)}
        >
          <option value="">Todos os providers</option>
          {Object.entries(providers).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar conta"
          value={account}
          onChange={filter(setAccount)}
        >
          <option value="">Todas as contas</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <input
          aria-label="Extensão"
          placeholder="Extensão: jpg"
          value={ext}
          onChange={filter(setExt)}
        />
      </div>
      {error && <p role="alert">{error}</p>}
      <p className="muted">{result.total} origem(ns) encontrada(s)</p>
      {result.items.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Origem</th>
                <th>Tamanho</th>
                <th>Sincronizado</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((f) => (
                <tr key={f.id}>
                  <td>
                    <button
                      className="file-name"
                      onClick={async () => {
                        setSelected(f);
                        setOrigins([]);
                        try {
                          setOrigins(await api(`/files/${f.sha256}/origins`));
                        } catch (e) {
                          setError(e.message);
                        }
                      }}
                    >
                      <FolderOpen size={17} />
                      {f.name}
                    </button>
                    <small>{f.original_path}</small>
                  </td>
                  <td>
                    {f.account_name}
                    <small>{providers[f.provider]}</small>
                  </td>
                  <td>{bytes(f.size)}</td>
                  <td>{date(f.synced_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          icon={FolderOpen}
          title="Nenhum arquivo encontrado"
          text="Sincronize uma conta ou ajuste os filtros para encontrar seus arquivos."
        />
      )}
      <Pagination
        page={page}
        setPage={setPage}
        hasNext={(page + 1) * 100 < result.total}
      />
      {selected && (
        <Modal title={selected.name} onClose={() => setSelected(null)}>
          <p>Cópia local</p>
          <code>{selected.local_path}</code>
          <p>SHA-256</p>
          <code>{selected.sha256}</code>
          <h3>Origens deste conteúdo</h3>
          {origins.map((o) => (
            <p key={o.id}>
              <strong>{o.account_name}</strong>
              <br />
              {o.original_path}
            </p>
          ))}
        </Modal>
      )}
    </>
  );
}
function Modal({ title, onClose, children }) {
  const ref = React.useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog ref={ref} onCancel={onClose}>
      <div className="modal-heading">
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Fechar">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function AccountModal({ api, onClose, onSave }) {
  const [provider, setProvider] = useState("google_drive");
  const [remotes, setRemotes] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api("/remotes")
      .then(setRemotes)
      .catch((e) => setError(e.message));
  }, [api]);
  const local = ["filesystem", "takeout"].includes(provider);
  const remoteType = {
    google_drive: "drive",
    onedrive: "onedrive",
    dropbox: "dropbox",
  }[provider];
  return (
    <Modal title="Adicionar conta" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const values = Object.fromEntries(new FormData(e.currentTarget));
          setSaving(true);
          try {
            await onSave({
              ...values,
              interval_minutes: Number(values.interval_minutes),
            });
          } finally {
            setSaving(false);
          }
        }}
      >
        <label>
          Nome da conta
          <input
            name="name"
            required
            placeholder="Ex.: Drive pessoal"
            maxLength={120}
          />
        </label>
        <label>
          Provider
          <select
            name="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            {Object.entries(providers).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        {local ? (
          <label>
            Caminho da origem
            <input
              key="local"
              name="location"
              required
              placeholder={
                provider === "takeout"
                  ? "takeout/exportacao.zip"
                  : "meu-dispositivo"
              }
            />
            <small>
              Pasta ou arquivo dentro de /sources, montado como somente leitura.
            </small>
          </label>
        ) : (
          <>
            <label>
              Conta autorizada pelo rclone
              <select key={provider} name="location" required defaultValue="">
                <option value="" disabled>
                  Selecione uma conta
                </option>
                {remotes
                  .filter((r) => r.type === remoteType)
                  .map((r) => (
                    <option key={r.name} value={`${r.name}:`}>
                      {r.name}
                    </option>
                  ))}
              </select>
            </label>
            <p className="help-text">
              Ainda não aparece? Autorize a conta no servidor seguindo as
              instruções abaixo. Depois, reabra este formulário.
            </p>
            <OAuthHelp api={api} />
          </>
        )}
        <label>
          Frequência
          <select name="interval_minutes" defaultValue="360">
            <option value="0">Somente manual</option>
            <option value="60">A cada hora</option>
            <option value="360">A cada 6 horas</option>
            <option value="1440">Diariamente</option>
          </select>
        </label>
        {error && <p role="alert">{error}</p>}
        <button className="primary full-width" disabled={saving}>
          {saving ? "Adicionando…" : "Adicionar conta"}
        </button>
      </form>
    </Modal>
  );
}
function OAuthHelp({ api }) {
  const [provider, setProvider] = useState("google_drive");
  const [name, setName] = useState("");
  const [session, setSession] = useState(null);
  const [answer, setAnswer] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  async function start() {
    setError("");
    try { setSession(await api("/oauth/start", { method: "POST", body: JSON.stringify({ provider, name }) })); }
    catch (e) { setError(e.message); }
  }
  async function continueWizard() {
    setError("");
    try {
      const next = await api(`/oauth/${session.session}/continue`, { method: "POST", body: JSON.stringify({ result: answer }) });
      if (next.complete) { setDone(`Conta ${next.remote} autorizada. Feche e reabra o formulário para selecioná-la.`); setSession(null); }
      else { setSession(next); setAnswer(""); }
    } catch (e) { setError(e.message); }
  }
  const question = session?.question;
  return (
    <details className="oauth-help">
      <summary>Autorizar ou reautenticar uma conta pelo navegador</summary>
      <p>O assistente do rclone faz as perguntas aqui. Quando aparecer um link OAuth, abra-o, autorize a conta e cole somente a resposta solicitada.</p>
      <div className="oauth-form"><select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={!!session}><option value="google_drive">Google Drive</option><option value="onedrive">OneDrive</option><option value="dropbox">Dropbox</option></select><input value={name} onChange={(e) => setName(e.target.value)} disabled={!!session} placeholder="Nome da conta (ex.: drive-pessoal)"/><button type="button" className="secondary" onClick={start} disabled={!!session || !name}>Começar autorização</button></div>
      {question && <div className="oauth-question"><strong>{question.name}</strong><p>{question.help}</p>{question.examples?.length > 0 && <small>Opções: {question.examples.map((e) => e.Value || e.Help || e).join(" · ")}</small>}<textarea value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={question.default != null ? `Padrão: ${question.default}` : "Cole a resposta do rclone"} rows="4"/><button type="button" className="primary" onClick={continueWizard} disabled={question.required && !answer}>Continuar</button></div>}
      {done && <p className="oauth-done">{done}</p>}
      {error && <p role="alert">{error}</p>}
    </details>
  );
}
function Logs({ api, job, onClose }) {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    let after = 0;
    async function read() {
      try {
        const rows = await api(`/jobs/${job.id}/logs?after=${after}`);
        if (alive && rows.length) {
          after = rows.at(-1).id;
          setLogs((old) => [...old, ...rows]);
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    }
    read();
    const timer = setInterval(read, 2000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [api, job.id]);
  return (
    <Modal title={`Logs · ${job.account_name}`} onClose={onClose}>
      <div className="logs">
        {logs.map((l) => (
          <p key={l.id} className={l.level}>
            <time>{date(l.created_at)}</time> {l.message}
          </p>
        ))}
        {!logs.length && !error && <LoaderCircle className="spin" />}
        {error && <p role="alert">{error}</p>}
      </div>
    </Modal>
  );
}
function SettingsView({ api, logout }) {
  const [settings, setSettings] = useState(null);
  const [update, setUpdate] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    api("/settings")
      .then(setSettings)
      .catch((e) => setError(e.message));
  }, [api]);
  useEffect(() => {
    api("/update").then(setUpdate).catch(() => setUpdate(null));
  }, [api]);
  return (
    <div className="settings-grid">
      {update?.update_available && (
        <section className="settings-panel update-panel">
          <RefreshCw size={26} />
          <h2>Nova versão disponível</h2>
          <p>Esta instalação está em {update.current}; a versão {update.latest} já foi publicada.</p>
          <a className="primary" href={update.release_url} target="_blank" rel="noreferrer">Ver atualização</a>
          <p className="muted">Depois de atualizar a imagem no ZimaOS, os dados em /DATA/CloudSync permanecem intactos.</p>
        </section>
      )}
      <section className="settings-panel">
        <HardDrive size={26} />
        <h2>Armazenamento persistente</h2>
        <p>
          Banco, configurações, logs e arquivos permanecem no volume do servidor
          durante as atualizações.
        </p>
        <code>{settings?.root || "/DATA/CloudSync"}</code>
        <p>Versão {settings?.version || "…"}</p>
      </section>
      <section className="settings-panel">
        <FolderOpen size={26} />
        <h2>Biblioteca do Immich</h2>
        <p>
          Adicione a pasta de dados como External Library no Immich e monte-a
          como somente leitura.
        </p>
        <code>/DATA/CloudSync/data:/mnt/cloud-sync:ro</code>
        <button
          className="text-button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(
                "/DATA/CloudSync/data:/mnt/cloud-sync:ro",
              );
              setCopied(true);
            } catch {
              setError("Copie o caminho exibido acima.");
            }
          }}
        >
          <Copy size={16} />
          {copied ? "Copiado" : "Copiar volume"}
        </button>
      </section>
      <section className="settings-panel">
        <ShieldCheck size={26} />
        <h2>Acesso ao servidor</h2>
        <p>
          O token é mantido na sessão atual. Configure HTTPS no reverse proxy
          para acessar por domínio.
        </p>
        <button className="secondary" onClick={logout}>
          Sair e trocar token
        </button>
      </section>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
