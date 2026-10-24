import { useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { Camera, Check, X, AlertCircle, ImagePlus } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { submitImageInference } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import './ScanCapture.css';

export default function ScanCapture() {
  const navigate = useNavigate();
  const { user, growthStage } = useAuth();
  const { t } = useLanguage();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const fileInputRef = useRef(null);
  const capturedBlobRef = useRef(null);

  // 'choosing' shows the Take Photo / Upload Photo sheet before anything
  // else happens — the live camera only starts once the farmer picks it.
  const [mode, setMode] = useState('choosing'); // choosing | camera | upload
  const [preview, setPreview] = useState(null);
  const [cameraStatus, setCameraStatus] = useState('starting'); // starting | live | denied | unsupported
  const [analyzing, setAnalyzing] = useState(false);
  const [scanError, setScanError] = useState('');
  // Collected here, BEFORE the scan, because it's an INPUT to the affected-area
  // math (app/routers/inference.py's /image endpoint), not something to type in
  // after the result already came back — the result screen only ever displays
  // what was actually submitted.
  const [fieldSize, setFieldSize] = useState('');
  const [fieldSizeUnit, setFieldSizeUnit] = useState('ha');

  useEffect(() => {
    if (mode !== 'camera' || preview) return undefined; // don't keep the camera running once a photo is captured

    let cancelled = false;

    async function startCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraStatus('unsupported');
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        setCameraStatus('live');
      } catch (err) {
        setCameraStatus('denied');
      }
    }

    startCamera();

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, [mode, preview]);

  // The <video> element only mounts once cameraStatus becomes 'live', so the
  // stream must be attached in a separate effect that runs after that mount,
  // not inside startCamera() where the ref would still be null.
  useEffect(() => {
    if (cameraStatus === 'live' && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [cameraStatus]);

  // Runs the real /api/inference/image request once the farmer confirms the
  // captured/selected photo. The overlay stays up until the response comes
  // back rather than a fixed timeout.
  useEffect(() => {
    if (!analyzing) return undefined;
    let cancelled = false;

    async function runInference() {
      try {
        const blob = capturedBlobRef.current;
        const typed = Number(fieldSize);
        const hasTyped = fieldSize.trim() !== '' && Number.isFinite(typed) && typed > 0;
        const fieldSizeHa = hasTyped ? (fieldSizeUnit === 'm2' ? typed / 10000 : typed) : null;
        const result = blob
          ? await submitImageInference(blob, user?.municipality, growthStage, fieldSizeHa)
          : null;
        if (cancelled) return;
        navigate('/scan/result', { state: { inference: result, photo: blob } });
      } catch (err) {
        if (cancelled) return;
        setScanError(err.message || t('scanErrorUpload'));
        setAnalyzing(false);
      }
    }

    runInference();
    return () => {
      cancelled = true;
    };
    // user.municipality/growthStage/fieldSize(Unit) are read once at submit
    // time by design — this effect is gated on `analyzing` (a one-shot
    // trigger from tapping the shutter), not meant to re-fire mid-upload if
    // any of them change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyzing, navigate]);

  const capturePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || cameraStatus !== 'live') return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (blob) {
        capturedBlobRef.current = blob;
        setPreview(URL.createObjectURL(blob));
      }
    }, 'image/jpeg', 0.9);

    // Stop the live stream immediately; the captured frame replaces it.
    streamRef.current?.getTracks().forEach((track) => track.stop());
  };

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      capturedBlobRef.current = file;
      setPreview(URL.createObjectURL(file));
    }
  };

  const retake = () => {
    capturedBlobRef.current = null;
    setPreview(null);
    setScanError('');
    setCameraStatus('starting');
    if (mode === 'upload') fileInputRef.current?.click();
  };

  const chooseCamera = () => {
    setMode('camera');
    setCameraStatus('starting');
  };

  const chooseUpload = () => {
    setMode('upload');
    fileInputRef.current?.click();
  };

  return (
    <div className="scan-screen">
      <ScreenHeader title={t('scanCaptureTitle')} onBack={() => navigate('/home')} />

      <div className="scan-body">
        {mode === 'choosing' ? (
          <div className="scan-setup">
            <div className="scan-step">
              <span className="scan-step-head">
                <span className="scan-step-number">1</span>
                <span className="scan-step-title">{t('scanStepFieldSize')}</span>
                <span className="scan-step-badge">{t('scanFieldSizeOptionalBadge')}</span>
              </span>
              <div className="scan-field-size-card">
                <label htmlFor="scan-field-size-input">{t('scanFieldSizePrompt')}</label>
                <div className="scan-field-size-row">
                  <input
                    id="scan-field-size-input"
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="any"
                    placeholder={fieldSizeUnit === 'ha' ? 'e.g. 1.5' : 'e.g. 5000'}
                    value={fieldSize}
                    onChange={(e) => setFieldSize(e.target.value)}
                  />
                  <div className="scan-field-unit-toggle" role="group" aria-label={t('scanFieldSizeLabel')}>
                    <button
                      type="button"
                      className={fieldSizeUnit === 'ha' ? 'is-active' : ''}
                      onClick={() => setFieldSizeUnit('ha')}
                    >
                      {t('scanResultUnitHa')}
                    </button>
                    <button
                      type="button"
                      className={fieldSizeUnit === 'm2' ? 'is-active' : ''}
                      onClick={() => setFieldSizeUnit('m2')}
                    >
                      m²
                    </button>
                  </div>
                </div>
                <p className="scan-field-size-hint">{t('scanFieldSizeHint')}</p>
              </div>
            </div>

            <div className="scan-step">
              <span className="scan-step-head">
                <span className="scan-step-number">2</span>
                <span className="scan-step-title">{t('scanStepAddPhoto')}</span>
              </span>
              <div className="scan-choice-cards">
                <button className="scan-choice-card scan-choice-card-primary" onClick={chooseCamera}>
                  <span className="scan-choice-card-icon">
                    <Camera size={20} />
                  </span>
                  <strong>{t('scanChoiceCameraTitle')}</strong>
                  <small>{t('scanChoiceCameraSubtitle')}</small>
                </button>
                <button className="scan-choice-card" onClick={chooseUpload}>
                  <span className="scan-choice-card-icon">
                    <ImagePlus size={20} />
                  </span>
                  <strong>{t('scanChoiceUploadTitle')}</strong>
                  <small>{t('scanChoiceUploadSubtitle')}</small>
                </button>
              </div>
            </div>

            <div className="scan-accuracy">
              <span className="scan-accuracy-title">{t('scanAccuracyTitle')}</span>
              <div className="scan-accuracy-examples">
                <span className="scan-example-chip scan-example-good">{t('scanTipGoodExample')}</span>
                <span className="scan-example-chip scan-example-bad">{t('scanTipBadExample')}</span>
              </div>
              <div className="scan-accuracy-captions">
                <span className="scan-accuracy-caption scan-accuracy-caption-good">
                  <Check size={13} /> {t('scanGoodExampleCaption')}
                </span>
                <span className="scan-accuracy-caption scan-accuracy-caption-bad">
                  <X size={13} /> {t('scanBadExampleCaption')}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="scan-frame">
            {preview ? (
              <img src={preview} alt={t('scanCapturedAlt')} className="scan-frame-img" />
            ) : mode === 'camera' && cameraStatus === 'live' ? (
              <video ref={videoRef} autoPlay playsInline muted className="scan-frame-video" />
            ) : mode === 'camera' && cameraStatus === 'starting' ? (
              <div className="scan-frame-placeholder">
                <Camera size={40} color="rgba(255,255,255,0.5)" />
                <span className="scan-frame-status">{t('scanStarting')}</span>
              </div>
            ) : mode === 'camera' ? (
              <div className="scan-frame-placeholder scan-frame-error">
                <AlertCircle size={32} color="rgba(255,255,255,0.7)" />
                <span className="scan-frame-status">
                  {cameraStatus === 'denied' ? t('scanCameraDenied') : t('scanCameraUnsupported')}
                </span>
              </div>
            ) : (
              <button className="scan-frame-placeholder scan-frame-placeholder-btn" onClick={chooseUpload}>
                <ImagePlus size={40} color="rgba(255,255,255,0.5)" />
                <span className="scan-frame-status">{t('scanUploadPrompt')}</span>
              </button>
            )}

            <canvas ref={canvasRef} hidden />

            {preview && !analyzing && (
              <button className="scan-frame-clear" onClick={retake} aria-label="Retake photo">
                <X size={14} />
              </button>
            )}

            {analyzing && (
              <div className="scan-analyzing-overlay">
                <span className="scan-analyzing-spinner" />
                <span className="scan-analyzing-text">{t('scanAnalyzingOverlayText')}</span>
              </div>
            )}
          </div>
        )}

        {mode !== 'choosing' && (
          <>
            <h2>{t('scanInstructionsTitle')}</h2>
            <p className="scan-instructions">{t('scanInstructions')}</p>

            <ul className="scan-tips">
              <li>✓ {t('scanTipClose')}</li>
              <li>✓ {t('scanTipSteady')}</li>
            </ul>

            {scanError && <p className="scan-error">{scanError}</p>}

            {!preview && !analyzing && (
              <button className="scan-change-mode" onClick={() => setMode('choosing')}>
                {t('scanChangeMode')}
              </button>
            )}
          </>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={handleFile}
        />
      </div>

      {!analyzing && mode !== 'choosing' && (mode === 'camera' || preview) && (
        <button
          className="scan-shutter-ring"
          onClick={() => {
            if (preview) setAnalyzing(true);
            else if (cameraStatus === 'live') capturePhoto();
          }}
          aria-label={preview ? t('scanShutterScan') : t('scanShutterCapture')}
        >
          <span className="scan-shutter-ring-inner" />
        </button>
      )}
    </div>
  );
}
