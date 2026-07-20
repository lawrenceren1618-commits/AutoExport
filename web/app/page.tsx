import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <div className="card">
        <h1>AutoExport</h1>
        <p className="muted">
          订单 / 货代 / 报关 — 办公室端云端应用。工作总结与进度树仅后台可见。
        </p>
        <p>
          <Link className="btn" href="/admin/login">
            进入后台
          </Link>
        </p>
        <p className="muted">
          项目名 AutoExport；提交人 Office CP；SSH 别名 github.com-office-cp。
        </p>
      </div>
    </main>
  );
}
