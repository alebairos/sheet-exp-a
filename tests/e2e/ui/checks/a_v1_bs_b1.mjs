// b1 and the NFR, in a real browser: open big.csv (2001 rows x 12 columns), scroll with real mouse-wheel events
// over the grid to the last row and the last column, and see L2001 with its row and column headers. Each wheel
// step is timed from sending it to the next paint after it (timedStep): every one under 100 ms.
import { CALC, fail, bigCSV, openPage, cellText, seen, seenCell, frames, timedStep } from "./a_v1_bs_page.mjs";

const { b, js, until, done } = await openPage("big.csv", bigCSV());
try {
  await js(frames);
  const box = await js(`(() => { const r = document.getElementById("grid").getBoundingClientRect();
    return {x: Math.min(r.left + r.width / 2, innerWidth / 2), y: Math.min(r.top + 200, innerHeight / 2)}; })()`);
  const steps = [];
  const wheel = async (deltaX, deltaY) => {
    steps.push(await timedStep(b, js, () => b.send("Input.dispatchMouseEvent", { type: "mouseWheel", x: box.x, y: box.y, deltaX, deltaY })));
  };
  // Down: at most 400 steps of 400 px reach any layout of 2001 rows; the row must come into view.
  for (let i = 0; i < 400 && !(await js(seenCell("A2001"))); i++) await wheel(0, 400);
  if (!(await js(seenCell("A2001")))) fail(`after ${steps.length} wheel steps down over the grid, row 2001 (A2001) is still not visible`);
  // Right: column L comes into view, row 2001 stays.
  for (let i = 0; i < 100 && !(await js(seenCell("L2001"))); i++) await wheel(300, 0);
  if (!(await js(seenCell("L2001")))) fail("after wheel steps right over the grid, L2001 is still not visible");
  await until("L2001 shows its CSV value", cellText("L2001"), CALC.csv.L2001);
  await until("B2001 shows its CSV value", cellText("B2001"), CALC.csv.B2001);
  await until("the row header 2001 is visible next to it", seen("#grid th", "2001"), true, 10);
  await until("the column header L is visible above it", seen("#grid th", "L"), true, 10);
  // Back to the top: the first rows come back.
  for (let i = 0; i < 400 && !(await js(seenCell("A1"))); i++) await wheel(-3000, -400);
  if (!(await js(seenCell("A1")))) fail("scrolling back up and left never shows A1 again");
  const slow = steps.filter((t) => t >= 100);
  const ms = (t) => t.toFixed(1) + " ms";
  if (slow.length) fail(`${slow.length} of ${steps.length} scroll steps took 100 ms or more (slowest ${ms(Math.max(...slow))})`);
  const sorted = [...steps].sort((x, y) => x - y);
  console.log(`ok b1: scrolled to L2001 (${CALC.csv.L2001}) and back in ${steps.length} wheel steps; median ${ms(sorted[sorted.length >> 1])}, slowest ${ms(sorted.at(-1))}`);
  done(0);
} catch (e) { console.log("FAIL " + (e.stack || e)); done(1); }
