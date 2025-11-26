import GeometricBackground from '../GeometricBackground';

export default function GeometricBackgroundExample() {
  return (
    <div className="relative h-screen w-full overflow-hidden">
      <GeometricBackground />
      
      {/* Demo overlay content to show Glass UI compatibility */}
      <div className="relative z-10 flex items-center justify-center h-full">
        <div className="bg-white/20 backdrop-blur-lg border border-white/30 rounded-lg p-8 shadow-xl">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">
            Glass UI Demo Card
          </h2>
          <p className="text-gray-600 mb-4">
            This demonstrates how the geometric background works with Glass UI overlays.
            The background provides subtle visual interest without interfering with content.
          </p>
          <div className="bg-white/30 backdrop-blur-sm border border-white/40 rounded-md p-4">
            <p className="text-sm text-gray-700">
              Nested glass element showing layering compatibility
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}