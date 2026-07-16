import { authApi } from "@/lib/api";

export async function customerSignIn(email: string, password: string) {
  return authApi.customerLogin(email, password);
}

export type CustomerRegisterPayload = {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  city: string;
  district: string;
};

export async function customerRegister(payload: CustomerRegisterPayload) {
  return authApi.customerRegister(payload);
}

export async function firebaseSignOut() {
  await authApi.logout();
}
