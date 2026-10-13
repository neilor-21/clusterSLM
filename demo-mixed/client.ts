import { request } from "./api";

export function loadUser() {
    return request("/users");
}