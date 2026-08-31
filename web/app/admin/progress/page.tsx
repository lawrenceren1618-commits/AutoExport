import { redirect } from "next/navigation";

export default function AdminProgressRedirect() {
  redirect("/ops/progress");
}
