import { redirect } from "next/navigation";

export default function AdminFbaRedirect() {
  redirect("/ops/fba-track");
}
