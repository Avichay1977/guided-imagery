import './VolumeSlider.css'

function VolumeSlider({ icon, label, offHint, loudHint, value, onChange, disabled = false }) {
  return (
    <div className="form-group mix-group">
      <label className="form-label">
        <span className="mix-icon">{icon}</span>
        {label}
        <span className="mix-value">{value}%</span>
      </label>
      <input
        type="range"
        className="mix-slider"
        min="0"
        max="100"
        step="5"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="mix-hints">
        <span>{offHint}</span>
        <span>{loudHint}</span>
      </div>
    </div>
  )
}

export default VolumeSlider
