import Link from "next/link";

export default function HomePage() {
  return (
    <main className="ws-main">
      <header className="ws-hero">
        <p className="ws-brand">AutoExport</p>
        <h1>办公室发货单证</h1>
        <p className="ws-lead">
          作业前台仅「输入 / 输出」；生成前预检，外箱贴多仓确认后出三表。库务用于总表入库、仓头追踪与进度。
        </p>
        <p style={{ marginTop: "1.25rem" }}>
          <Link className="ws-btn" href="/workspace" style={{ textDecoration: "none" }}>
            进入作业
          </Link>
        </p>
        <p className="ws-meta" style={{ marginTop: "1rem" }}>
          <Link href="/ops/login">库务登录</Link>
        </p>
      </header>
    </main>
  );
}
