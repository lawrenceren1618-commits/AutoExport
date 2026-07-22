import Link from "next/link";

export function AdminNav() {
  return (
    <nav className="admin-nav">
      <Link href="/admin/progress">工作总结</Link>
      <Link href="/admin/fba-track">FBA仓头/追踪码</Link>
      <Link href="/admin/master-import">人工总表导入</Link>
      <Link href="/">返回首页</Link>
    </nav>
  );
}
