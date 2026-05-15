import { useState, useRef, useCallback } from 'react'

const API = 'http://localhost:8000'

// ── Tiny components ──────────────────────────────────────────────────────────

function Spinner() {
  return (
    <span style={{
      display: 'inline-block', width: 14, height: 14,
      border: '2px solid #3d4752', borderTopColor: 'var(--accent)',
      borderRadius: '50%', animation: 'spin 0.7s linear infinite',
      verticalAlign: 'middle', marginRight: 8,
    }} />
  )
}

function Badge({ label, color }) {
  const colors = {
    red:    { bg: 'var(--red-dim)',   border: '#ff4d4d55', text: 'var(--red)' },
    green:  { bg: 'var(--green-dim)', border: '#3ddc8455', text: 'var(--green)' },
    orange: { bg: '#ff9a3c18',        border: '#ff9a3c55', text: 'var(--orange)' },
    blue:   { bg: '#4d9fff18',        border: '#4d9fff55', text: 'var(--blue)' },
  }
  const c = colors[color] || colors.blue
  return (
    <span style={{
      fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500,
      padding: '3px 10px', borderRadius: 4,
      background: c.bg, border: `1px solid ${c.border}`, color: c.text,
      letterSpacing: '0.08em', textTransform: 'uppercase',
    }}>{label}</span>
  )
}

function ScoreBar({ score }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.75 ? 'var(--red)' : score >= 0.4 ? 'var(--orange)' : 'var(--green)'
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 11, color: 'var(--text2)', letterSpacing: '0.06em' }}>VULNERABILITY SCORE</span>
        <span style={{ fontSize: 13, fontWeight: 600, color }}>{pct}%</span>
      </div>
      <div style={{ height: 4, background: 'var(--bg3)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, borderRadius: 2,
          background: color, transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
        }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 10, color: 'var(--text3)' }}>safe</span>
        <span style={{ fontSize: 10, color: 'var(--text3)' }}>threshold 75%</span>
        <span style={{ fontSize: 10, color: 'var(--text3)' }}>critical</span>
      </div>
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [code, setCode]               = useState('')
  const [isDragging, setIsDragging]   = useState(false)
  const [fileName, setFileName]       = useState(null)

  const [step, setStep]               = useState('idle')   // idle | analyzing | explained | fixing | done | error
  const [verdict, setVerdict]         = useState(null)
  const [explanation, setExplanation] = useState('')
  const [fixedCode, setFixedCode]     = useState('')
  const [errorMsg, setErrorMsg]       = useState('')

  const fileInputRef = useRef(null)
  const textareaRef  = useRef(null)

  // ── File drop ──────────────────────────────────────────────────────────────
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0]
    if (!file) return
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (ev) => setCode(ev.target.result)
    reader.readAsText(file)
  }, [])

  // ── Reset ─────────────────────────────────────────────────────────────────
  const reset = () => {
    setStep('idle'); setVerdict(null)
    setExplanation(''); setFixedCode(''); setErrorMsg('')
  }

  const handleCodeChange = (v) => { setCode(v); reset() }

  // ── Step 1: Analyze ───────────────────────────────────────────────────────
  const analyze = async () => {
    if (!code.trim()) return
    reset()
    setStep('analyzing')
    try {
      const res = await fetch(`${API}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      const data = await res.json()
      setVerdict(data)

      if (data.vulnerable) {
        // Auto-run explain
        setStep('explaining')
        const res2 = await fetch(`${API}/explain`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code }),
        })
        if (!res2.ok) throw new Error((await res2.json()).detail)
        const d2 = await res2.json()
        setExplanation(d2.explanation)
        setStep('explained')
      } else {
        setStep('safe')
      }
    } catch (err) {
      setErrorMsg(err.message)
      setStep('error')
    }
  }

  // ── Step 2: Fix ───────────────────────────────────────────────────────────
  const getFixedCode = async () => {
    setStep('fixing')
    try {
      const res = await fetch(`${API}/fix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, explanation }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      const data = await res.json()
      setFixedCode(data.fixed_code)
      setStep('done')
    } catch (err) {
      setErrorMsg(err.message)
      setStep('error')
    }
  }

  const copyToClipboard = (text) => navigator.clipboard.writeText(text)

  const isLoading = ['analyzing', 'explaining', 'fixing'].includes(step)

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%,100% { opacity: 1; } 50% { opacity: 0.4; }
        }
        .fade-up { animation: fadeUp 0.4s ease forwards; }
        .btn {
          display: inline-flex; align-items: center; gap: 6px;
          font-family: var(--mono); font-size: 13px; font-weight: 500;
          padding: 10px 20px; border-radius: 6px; border: none;
          cursor: pointer; transition: all 0.15s; letter-spacing: 0.04em;
        }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .btn-primary {
          background: var(--accent); color: #0a0c0f;
        }
        .btn-primary:not(:disabled):hover { background: var(--accent2); }
        .btn-ghost {
          background: transparent; color: var(--text2);
          border: 1px solid var(--border2);
        }
        .btn-ghost:not(:disabled):hover { border-color: var(--text2); color: var(--text); }
        .btn-red {
          background: var(--red-dim); color: var(--red);
          border: 1px solid #ff4d4d33;
        }
        .btn-red:not(:disabled):hover { background: #ff4d4d33; }
        .code-area {
          width: 100%; min-height: 260px; resize: vertical;
          background: var(--bg2); color: var(--text);
          border: 1.5px solid var(--border); border-radius: 8px;
          font-family: var(--mono); font-size: 13px; line-height: 1.7;
          padding: 20px; outline: none;
          transition: border-color 0.15s;
          tab-size: 2;
        }
        .code-area:focus { border-color: var(--border2); }
        .code-area.drag-over { border-color: var(--accent); background: #e8ff5a08; }
        .panel {
          background: var(--bg2); border: 1px solid var(--border);
          border-radius: 8px; overflow: hidden;
        }
        .panel-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 12px 16px; border-bottom: 1px solid var(--border);
          background: var(--bg3);
        }
        .panel-title { font-size: 11px; color: var(--text2); letter-spacing: 0.1em; text-transform: uppercase; font-weight: 500; }
        .panel-body { padding: 20px; font-size: 13px; line-height: 1.8; white-space: pre-wrap; }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .status-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
      `}</style>

      <div style={{ minHeight: '100vh', padding: '0 0 80px' }}>

        {/* ── Header ── */}
        <header style={{
          borderBottom: '1px solid var(--border)',
          padding: '18px 40px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          position: 'sticky', top: 0, zIndex: 10,
          background: 'rgba(10,12,15,0.92)', backdropFilter: 'blur(12px)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'var(--accent)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: 16,
            }}>⚡</div>
            <div>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 17, fontWeight: 700, color: '#fff', letterSpacing: '-0.01em' }}>
                VulnScope
              </div>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 1 }}>GraphCodeBERT + Qwen2.5-Coder</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--green)', display: 'inline-block', animation: 'pulse 2s infinite' }} />
            <span style={{ fontSize: 11, color: 'var(--text2)' }}>pipeline ready</span>
          </div>
        </header>

        <main style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px' }}>

          {/* ── Input section ── */}
          <section>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
              <label style={{ fontSize: 11, color: 'var(--text2)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Source Code
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                {fileName && (
                  <span style={{ fontSize: 11, color: 'var(--accent)', padding: '3px 8px', background: '#e8ff5a11', border: '1px solid #e8ff5a33', borderRadius: 4 }}>
                    📄 {fileName}
                  </span>
                )}
                <button
                  className="btn btn-ghost"
                  style={{ padding: '5px 12px', fontSize: 11 }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  ↑ Upload file
                </button>
                <input
                  ref={fileInputRef} type="file" hidden
                  accept=".c,.cpp,.cc,.cxx,.h,.py,.js,.ts,.java,.go,.rs,.php"
                  onChange={handleDrop}
                />
              </div>
            </div>

            <textarea
              ref={textareaRef}
              className={`code-area ${isDragging ? 'drag-over' : ''}`}
              value={code}
              onChange={(e) => handleCodeChange(e.target.value)}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              placeholder={`// Paste your code here, or drag & drop a file\n// Supports C, C++, Python, Java, Go, Rust, PHP, JS/TS\n\nvoid example(char *input) {\n    char buffer[64];\n    strcpy(buffer, input); // ← something like this\n}`}
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === 'Tab') {
                  e.preventDefault()
                  const s = e.target.selectionStart
                  const val = code
                  setCode(val.substring(0, s) + '  ' + val.substring(e.target.selectionEnd))
                  setTimeout(() => { e.target.selectionStart = e.target.selectionEnd = s + 2 }, 0)
                }
              }}
            />

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
              <button
                className="btn btn-primary"
                onClick={analyze}
                disabled={isLoading || !code.trim()}
              >
                {isLoading && <Spinner />}
                {step === 'analyzing'  ? 'Scanning...' :
                 step === 'explaining' ? 'Analyzing with Qwen...' :
                 step === 'fixing'     ? 'Generating fix...' :
                 '⚡ Analyze'}
              </button>

              {code && (
                <button className="btn btn-ghost" onClick={() => { setCode(''); setFileName(null); reset() }}>
                  Clear
                </button>
              )}

              <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 'auto' }}>
                {code.split('\n').length} lines · {code.length} chars
              </span>
            </div>
          </section>

          {/* ── Results ── */}
          {step !== 'idle' && step !== 'analyzing' && (
            <section className="fade-up" style={{ marginTop: 36 }}>

              {/* Error */}
              {step === 'error' && (
                <div style={{
                  padding: 20, borderRadius: 8,
                  background: 'var(--red-dim)', border: '1px solid #ff4d4d44',
                  color: 'var(--red)', fontSize: 13,
                }}>
                  <strong>Error:</strong> {errorMsg}
                  <div style={{ marginTop: 8, fontSize: 11, color: '#ff9a9a' }}>
                    Make sure the backend is running: <code>python main.py</code>
                    {errorMsg.includes('Ollama') && <><br/>And Ollama is running: <code>ollama serve</code></>}
                  </div>
                </div>
              )}

              {/* Safe */}
              {step === 'safe' && verdict && (
                <div style={{
                  padding: 24, borderRadius: 8,
                  background: 'var(--green-dim)', border: '1px solid #3ddc8444',
                }}>
                  <div className="status-row">
                    <span className="dot" style={{ background: 'var(--green)' }} />
                    <span style={{ fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 700, color: 'var(--green)' }}>
                      No vulnerability detected
                    </span>
                    <Badge label="Non-Vulnerable" color="green" />
                  </div>
                  <ScoreBar score={verdict.score} />
                  <p style={{ marginTop: 16, fontSize: 12, color: 'var(--text2)', lineHeight: 1.7 }}>
                    GraphCodeBERT did not flag this code as vulnerable (score {Math.round(verdict.score * 100)}%, threshold 75%).
                    This is a statistical model — always combine with manual review for critical code.
                  </p>
                </div>
              )}

              {/* Vulnerable — explanation */}
              {['explained', 'fixing', 'done'].includes(step) && verdict && (
                <>
                  {/* Verdict banner */}
                  <div style={{
                    padding: 20, borderRadius: 8, marginBottom: 20,
                    background: 'var(--red-dim)', border: '1px solid #ff4d4d44',
                  }}>
                    <div className="status-row">
                      <span className="dot" style={{ background: 'var(--red)', animation: 'pulse 1.5s infinite' }} />
                      <span style={{ fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 700, color: 'var(--red)' }}>
                        Vulnerability Detected
                      </span>
                      <Badge label="Vulnerable" color="red" />
                    </div>
                    <ScoreBar score={verdict.score} />
                  </div>

                  {/* Explanation panel */}
                  {explanation && (
                    <div className="panel fade-up" style={{ marginBottom: 20 }}>
                      <div className="panel-header">
                        <span className="panel-title">🔍 Qwen2.5-Coder Analysis</span>
                        <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }}
                          onClick={() => copyToClipboard(explanation)}>
                          Copy
                        </button>
                      </div>
                      <div className="panel-body" style={{ color: 'var(--text)' }}>
                        {explanation}
                      </div>
                    </div>
                  )}

                  {/* Fix prompt */}
                  {step === 'explained' && (
                    <div className="fade-up" style={{
                      padding: 20, borderRadius: 8,
                      background: 'var(--bg2)', border: '1px solid var(--border2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
                      flexWrap: 'wrap',
                    }}>
                      <div>
                        <div style={{ fontFamily: 'var(--sans)', fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                          Want the fixed code?
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                          Qwen will patch the vulnerability and annotate every change.
                        </div>
                      </div>
                      <button className="btn btn-red" onClick={getFixedCode}>
                        🔧 Generate fixed code
                      </button>
                    </div>
                  )}

                  {/* Fixing spinner */}
                  {step === 'fixing' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 20, color: 'var(--text2)', fontSize: 13 }}>
                      <Spinner /> Qwen is writing the patch...
                    </div>
                  )}

                  {/* Fixed code panel */}
                  {step === 'done' && fixedCode && (
                    <div className="panel fade-up">
                      <div className="panel-header">
                        <span className="panel-title">🔧 Fixed Code</span>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }}
                            onClick={() => copyToClipboard(fixedCode)}>
                            Copy
                          </button>
                          <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }}
                            onClick={() => {
                              const blob = new Blob([fixedCode], { type: 'text/plain' })
                              const url  = URL.createObjectURL(blob)
                              const a    = document.createElement('a')
                              a.href = url; a.download = `fixed_${fileName || 'code.c'}`;
                              a.click(); URL.revokeObjectURL(url)
                            }}>
                            ↓ Download
                          </button>
                        </div>
                      </div>
                      <div className="panel-body" style={{
                        background: 'var(--bg)', color: 'var(--text)',
                        fontFamily: 'var(--mono)', fontSize: 12.5,
                        maxHeight: 500, overflowY: 'auto',
                      }}>
                        {fixedCode}
                      </div>
                    </div>
                  )}
                </>
              )}
            </section>
          )}

          {/* ── How it works (idle state) ── */}
          {step === 'idle' && !code && (
            <section style={{ marginTop: 60, opacity: 0.7 }}>
              <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 24 }}>
                How it works
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                {[
                  { n: '01', title: 'Scan', desc: 'GraphCodeBERT analyzes your code for vulnerability patterns learned from 180k real CVEs.' },
                  { n: '02', title: 'Explain', desc: 'If flagged, Qwen2.5-Coder identifies the exact vulnerability type, root cause, and attack surface.' },
                  { n: '03', title: 'Fix', desc: 'On request, Qwen generates a patched version with inline comments on every changed line.' },
                ].map(({ n, title, desc }) => (
                  <div key={n} style={{
                    padding: 20, borderRadius: 8,
                    background: 'var(--bg2)', border: '1px solid var(--border)',
                  }}>
                    <div style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600, marginBottom: 8, letterSpacing: '0.1em' }}>{n}</div>
                    <div style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>{title}</div>
                    <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.7 }}>{desc}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

        </main>
      </div>
    </>
  )
}
