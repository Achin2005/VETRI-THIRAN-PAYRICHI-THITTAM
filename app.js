const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const money = n => "₹" + Number(n || 0).toLocaleString("en-IN");

function renderPlan(d, el) {
  if (d.error) { el.innerHTML = `<div class="card err">😕 ${esc(d.error)}</div>`; return; }
  let h = `<div class="summary"><div><small>Total budget</small><b>${money(d.total_budget)}</b></div>
           <div><small>Money left</small><b>${money(d.remaining_budget)}</b></div></div>`;
  if (d.outfit) h += `<div class="card">👗 <b>Your outfit:</b> ${esc(d.outfit)}</div>`;
  (d.sections || []).forEach((s, i) => {
    h += `<div class="card c${i % 4}"><h3>${esc(s.title)} <span class="pill">${money(s.allocation)}</span></h3>`;
    (s.items || []).forEach(it => {
      h += `<div class="item"><div><b>${esc(it.name)}</b> ${it.quantity > 1 ? "× " + esc(it.quantity) : ""}
        <p>${esc(it.description)}</p><div class="links">` +
        Object.entries(it.links || {}).map(([k, u]) => `<a target="_blank" rel="noopener" href="${esc(u)}">${esc(k)}</a>`).join("") +
        `</div></div><div class="price">${money(it.price)}</div></div>`;
    });
    h += `</div>`;
  });
  if ((d.tips || []).length) h += `<div class="card tips"><h3>💡 Smart tips</h3><ul>${d.tips.map(t => `<li>${esc(t)}</li>`).join("")}</ul></div>`;
  el.innerHTML = h;
}

const form = document.getElementById("plan-form");
if (form) {
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const out = document.getElementById("result");
    out.innerHTML = `<div class="card">⏳ Gemini is planning your budget… this takes a few seconds.</div>`;
    out.scrollIntoView({ behavior: "smooth" });
    try {
      const r = await fetch(form.dataset.action, { method: "POST", body: new FormData(form) });
      renderPlan(await r.json(), out);
    } catch (err) { renderPlan({ error: "Network problem. Is the server running?" }, out); }
  });
}
