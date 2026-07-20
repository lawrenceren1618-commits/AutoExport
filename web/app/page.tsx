import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <div className="card">
        <h1>office-cp-ofce</h1>
        <p className="muted">
          订单 / 货代 / 报关 — 办公室端云端应用。业务进度树仅后台可见。
        </p>
        <p>
          <Link className="btn" href="/admin/login">
            进入后台
          </Link>
        </p>
        <p className="muted">
          OFCE_ENV 应为 office；数据使用独立 Supabase 项目 office-cp-ofce。
        </p>
      </div>
    </main>
  );
}
