import { ApiClient3 } from './apiClient3';
export * from './apiShared';

// ApiService is split across apiShared + apiClient0..3 (inheritance chain) to keep
// every file under the 800-line cap. All 260 static methods remain reachable as
// ApiService.<method>() via static inheritance.
export default class ApiService extends ApiClient3 {}
