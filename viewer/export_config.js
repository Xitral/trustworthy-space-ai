// Configure Cesium before app.js creates the viewer.
// Screenshot export depends on the browser keeping the WebGL drawing buffer
// available after rendering. This wrapper injects preserveDrawingBuffer without
// changing the rest of the viewer initialization code.
(function configureBeaconExportRendering() {
  if (!window.Cesium?.Viewer || window.__BEACON_PRESERVE_DRAWING_BUFFER_CONFIGURED__) return;

  const OriginalViewer = window.Cesium.Viewer;

  function ExportReadyViewer(container, options = {}) {
    const contextOptions = options.contextOptions || {};
    const webgl = contextOptions.webgl || {};
    const exportReadyOptions = {
      ...options,
      contextOptions: {
        ...contextOptions,
        webgl: {
          ...webgl,
          preserveDrawingBuffer: true,
        },
      },
    };

    const viewer = new OriginalViewer(container, exportReadyOptions);
    viewer.__BEACON_PRESERVE_DRAWING_BUFFER__ = true;
    return viewer;
  }

  ExportReadyViewer.prototype = OriginalViewer.prototype;
  Object.setPrototypeOf(ExportReadyViewer, OriginalViewer);

  window.Cesium.Viewer = ExportReadyViewer;
  window.__BEACON_PRESERVE_DRAWING_BUFFER_CONFIGURED__ = true;
})();
