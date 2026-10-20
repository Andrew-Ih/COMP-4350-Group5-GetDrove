import { redirect } from "next/navigation";

import { AFTER_LOGIN } from "@/features/auth";

/**
 * The site's front door (#249): straight into the app, at the rider home. That page asks
 * logged-out visitors to log in first and brings them back, so `/` opens the login page
 * for them and the rider home for anyone already logged in. The service status list that
 * used to be here is at /status.
 */
export default function HomePage(): never {
  redirect(AFTER_LOGIN);
}
