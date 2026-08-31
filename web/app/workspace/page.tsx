import Link from "next/link";
import { WorkspaceClient } from "./WorkspaceClient";

export default function WorkspacePage() {
  return (
    <main className="ws-main">
      <p className="ws-nav">
        <Link href="/">首页</Link>
        <span aria-hidden> · </span>
        <Link href="/workspace">作业</Link>
        <span aria-hidden> · </span>
        <Link href="/ops/login">库务</Link>
      </p>
      <WorkspaceClient />
    </main>
  );
}
