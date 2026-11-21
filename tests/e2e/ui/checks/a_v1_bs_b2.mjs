// b2, in a real browser with real keys: open the big workbook (big.csv's cells plus M1 =SUM(B2:B2001) and
// M2001 =B2001*2), walk with ArrowDown past the visible edge, PageDown to row 2001, PageUp, ArrowRight past
// column H to M; type 5 into B2001 and see M2001 and M1 recompute to Calc's answers. After every key the
// selected cell is the expected one and the user sees it.
import { CALC, fail, bigJSON, openPage, cellText, seenCell, selectedRef, press } from "./a_v1_bs_page.mjs";

const { b, js, until, done } = await openPage("big.json", bigJSON());
const at = (ref) => { const m = /^([A-Z]+)(\d+)$/.exec(ref); return { col: m[1], row: Number(m[2]) }; };
try {
  const r = await js(`(() => { const r = document.querySelector('#grid td[data-ref="A1"]').getBoundingClientRect();
    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()`);
  for (const type of ["mousePressed", "mouseReleased"]) await b.send("Input.dispatchMouseEvent", { type, ...r, button: "left", clickCount: 1 });
  await until("clicking A1 selects it", selectedRef, "A1");
  const key = async (k, want, what) => {
    await press(b, k);
    await until(`${what}: ${k} selects ${want}`, selectedRef, want, 50);
    await until(`${what}: after ${k} the user sees ${want}`, seenCell(want), true, 20);
  };
  // ArrowDown from A1 to A40: past the first screen, the view follows.
  for (let r = 2; r <= 40; r++) await key("ArrowDown", "A" + r, "ArrowDown");
  // PageDown: a page (at least 10 rows) at a time, the selection in view, until row 2001 or past it.
  let row = 40;
  for (let i = 0; i < 300 && row < 2001; i++) {
    await press(b, "PageDown");
    const ref = await js(selectedRef);
    if (!ref || at(ref).col !== "A" || at(ref).row < row + 10) fail(`PageDown from A${row} selects ${ref}, wanted column A at least 10 rows further`);
    await until(`after PageDown the user sees ${ref}`, seenCell(ref), true, 20);
    row = at(ref).row;
  }
  if (row < 2001) fail(`300 PageDowns from A40 reach only A${row}`);
  for (; row > 2001; row--) await key("ArrowUp", "A" + (row - 1), "back to row 2001");
  // PageUp: a page back, in view; PageDown and ArrowUp/Down return to A2001.
  await press(b, "PageUp");
  const up = await js(selectedRef);
  if (!up || at(up).col !== "A" || at(up).row > 1991) fail(`PageUp from A2001 selects ${up}, wanted column A at least 10 rows up`);
  await until(`after PageUp the user sees ${up}`, seenCell(up), true, 20);
  await press(b, "PageDown");
  row = at(await js(selectedRef)).row;
  for (; row > 2001; row--) await key("ArrowUp", "A" + (row - 1), "back to row 2001");
  for (; row < 2001; row++) await key("ArrowDown", "A" + (row + 1), "back to row 2001");
  // ArrowRight past the visible columns to M2001, where the formula reads B2001; ArrowLeft back to B2001.
  for (const c of "BCDEFGHIJKLM") await key("ArrowRight", c + "2001", "ArrowRight");
  await until(`M2001 (=B2001*2) shows Calc's ${CALC.before.M2001} before the edit`, cellText("M2001"), CALC.before.M2001);
  for (const c of "LKJIHGFEDCB") await key("ArrowLeft", c + "2001", "ArrowLeft");
  // Edit B2001: type 5 and Enter, as a user does.
  await press(b, "5");
  await press(b, "Enter");
  for (const c of "BCDEFGHIJKL") await key("ArrowRight", String.fromCharCode(c.charCodeAt(0) + 1) + "2002", "to M2002");
  await key("ArrowUp", "M2001", "to M2001");
  await until(`M2001 (=B2001*2) recomputes to Calc's ${CALC.after.M2001}`, cellText("M2001"), CALC.after.M2001);
  await until("after the recompute returns, the selection stays where the user moved it (M2001)", selectedRef, "M2001", 10);
  await until("B2001 holds the typed 5", cellText("B2001"), CALC.edit.B2001);
  // PageUp to the top: M1 (=SUM(B2:B2001)) shows Calc's new total.
  row = 2001;
  for (let i = 0; i < 300 && row > 1; i++) {
    await press(b, "PageUp");
    const ref = await js(selectedRef);
    if (!ref || at(ref).col !== "M" || (at(ref).row > row - 10 && at(ref).row !== 1)) fail(`PageUp from M${row} selects ${ref}`);
    row = at(ref).row;
  }
  await until("PageUp reaches M1 and the user sees it", seenCell("M1"), true, 20);
  await until(`M1 (=SUM(B2:B2001)) recomputes to Calc's ${CALC.after.M1}`, cellText("M1"), CALC.after.M1);
  console.log(`ok b2: keys reach A2001 and M2001, the view follows; B2001 := 5 gives M2001 ${CALC.after.M2001}, M1 ${CALC.after.M1} as in Calc`);
  done(0);
} catch (e) { console.log("FAIL " + (e.stack || e)); done(1); }
