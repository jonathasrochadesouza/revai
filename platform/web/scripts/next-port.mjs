/**
 * Port fallback wrapper for the Next.js server.
 *
 * Port 3000 is commonly held by other tools (Docker publishes ports on IPv4
 * while Next.js may bind IPv6 only), so a naive "is 3000 free" check is not
 * enough. This wrapper probes BOTH loopback stacks (127.0.0.1 and ::1) and
 * walks forward until it finds a port that is bindable on both, then spawns
 * the real `next` command pinned to that port.
 *
 * Usage: node scripts/next-port.mjs <dev|start> [extra next args...]
 * The starting port follows PORT when set, defaulting to 3000.
 */
import net from "node:net";
import { spawn } from "node:child_process";

function canBind(port, host) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, host);
  });
}

async function isFree(port) {
  return (await canBind(port, "127.0.0.1")) && (await canBind(port, "::1"));
}

const [command = "dev", ...extraArgs] = process.argv.slice(2);
const base = Number(process.env.PORT ?? "") || 3000;

let port = base;
for (let candidate = base; candidate < base + 50; candidate += 1) {
  if (await isFree(candidate)) {
    port = candidate;
    break;
  }
}

if (port !== base) {
  console.log(
    `> Port ${base} is in use; starting RevAI web on ${port} instead.`,
  );
}

const child = spawn("next", [command, "-p", String(port), ...extraArgs], {
  stdio: "inherit",
  shell: true,
});
child.on("exit", (code, signal) => {
  if (signal !== null) process.exit(0);
  process.exit(code ?? 1);
});
