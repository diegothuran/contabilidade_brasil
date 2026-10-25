import { UserManager, WebStorageStateStore } from "oidc-client-ts";

const logoutUrl = import.meta.env.VITE_OIDC_LOGOUT_URL;
const useIdToken = import.meta.env.VITE_OIDC_USE_ID_TOKEN === "1";

export const userManager = new UserManager({
  authority: import.meta.env.VITE_OIDC_AUTHORITY,
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID,
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: "openid profile email",
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  ...(logoutUrl ? { metadataSeed: { end_session_endpoint: logoutUrl } } : {}),
});

export async function completeSignIn(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  if (params.has("code") && params.has("state")) {
    await userManager.signinRedirectCallback();
    window.history.replaceState({}, document.title, "/app/rastro");
  }
}

export async function accessToken(): Promise<string> {
  const user = await userManager.getUser();
  if (!user || user.expired) {
    throw new Error("sessão expirada");
  }
  if (useIdToken) {
    if (!user.id_token) {
      throw new Error("sessão expirada");
    }
    return user.id_token;
  }
  return user.access_token;
}
