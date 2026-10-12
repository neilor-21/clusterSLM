import { request } from "./api";

export function loadUser(): string {
    return request("/users");
}