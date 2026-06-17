import { useEffect, useRef, useState } from "react";
import { api } from "../api";

export function LogDrawer({
  name,
  onClose,
  guard,
}: {
  name: string;
  onClose: () => void;
  guard: (p: Promise<unknown>) => Promise<void>;
}) {
  const [lines, setLines] = useState<string[]>([]);
  const [follow, setFollow] = useState(true);
  const bodyRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    let active = true;
    const load = () =>
      guard(
        api.logs(name, 400).then((r) => {
          if (active) setLines(r.lines);
        }),
      );
    load();
    const id = setInterval(load, 2000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [name, guard]);

  useEffect(() => {
    if (follow && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines, follow]);

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>{name} · logs</h2>
          <label className="follow">
            <input
              type="checkbox"
              checked={follow}
              onChange={(e) => setFollow(e.target.checked)}
            />
            Follow
          </label>
          <button className="ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <pre className="drawer-body" ref={bodyRef}>
          {lines.length ? lines.join("\n") : "No log output yet."}
        </pre>
      </div>
    </div>
  );
}
