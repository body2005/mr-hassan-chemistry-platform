/** Public DRM endpoints only; no content/communication keys belong here. */
export type VideoDrmDescriptor = {
  scheme: 'cbcs';
  widevine_license_url: string;
  fairplay_license_url: string;
  fairplay_certificate_url: string;
};
