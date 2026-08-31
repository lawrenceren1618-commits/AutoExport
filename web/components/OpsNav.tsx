import Link from "next/link";

export function OpsNav() {
  return (
    <nav className="admin-nav" aria-label="库务">
      <Link href="/workspace">作业</Link>
      <Link href="/ops/archives">发货存档</Link>
      <Link href="/ops/progress">进度树</Link>
      <Link href="/ops/fba-track">FBA仓头/追踪</Link>
      <Link href="/ops/master-import">总表入库</Link>
      <Link href="/">首页</Link>
    </nav>
  );
}
