import { redirect } from "next/navigation";

export default function AdminMasterRedirect() {
  redirect("/ops/master-import");
}
